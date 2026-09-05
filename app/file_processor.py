"""파일 형식 감지, 메타데이터 추출, 파일 변환 등 파일 처리 유틸리티."""

import re
import unicodedata
import zipfile
from io import BytesIO

from app.logger import get_logger

logger = get_logger("file_processor")

MAX_DECOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB (ZIP 압축해제)

_ZIP_MAGIC = b"PK\x03\x04"

# CSV 파일명 패턴: KakaoTalk_Chat_방이름_YYYY-MM-DD-HH-MM(-SS).csv
_CSV_FILENAME_RE = re.compile(
    r"KakaoTalk_Chat_(.+)_(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})"
)

# ZIP 파일명 패턴: Kakaotalk_Chat_방이름_YYYYMMDD_HHMMSS.zip
_ZIP_FILENAME_RE = re.compile(
    r"[Kk]akao[Tt]alk_Chat_(.+)_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})"
)

_LEADER_KEYWORD = "꿀성경 진행 방식 안내"

# 방 멤버 명단은 카톡 시스템 메시지에 그대로 남아 있다. CSV는 시스템 메시지도
# 한 행으로 들어오지만 TXT/ZIP은 parse_txt가 걸러내므로 원문에서 직접 읽는다.
_ACTOR = r"(?<![\w가-힣])([가-힣A-Za-z0-9 _\-.]{1,30}?)님이"
_INVITE_RE = re.compile(_ACTOR + r"\s+(.+?)(?:을|를)\s+초대했습니다")
_KICK_RE = re.compile(_ACTOR + r"\s+(.+?)(?:을|를)\s+내보냈습니다")
_NAME_IN_LIST_RE = re.compile(r"([^,]+?)님(?:,|과|와|$)")
_OWNER_RE = re.compile(r"(?<![\w가-힣])([가-힣A-Za-z0-9 _\-.]{1,30}?)님이\s+방장이\s+되어")
_JOIN_RE = re.compile(r"(?<![\w가-힣])([가-힣A-Za-z0-9 _\-.]{1,30}?)님이\s+들어왔습니다")
_LEAVE_RE = re.compile(r"(?<![\w가-힣])([가-힣A-Za-z0-9 _\-.]{1,30}?)님이\s+나갔습니다")
_DUAL_MARKER = "헷갈릴 수 있는 내용을 다시 안내드립니다"

# 투트랙 방은 인증마다 "구약"/"신약"을 적는다. 공지 문구는 기수마다 바뀌므로
# 인증 형태 자체를 신호로 쓴다. 실측: 투트랙 방 74.8%, 일반 방 0.2% 이하.
_DUAL_TRACK_WORDS = ("구약", "신약")
_DUAL_MIN_MESSAGES = 10
_DUAL_MIN_RATIO = 0.2


def detect_file_format(filename, file_bytes):
    """확장자와 매직바이트로 파일 형식을 판별한다. csv/txt/zip 중 하나를 반환."""
    if file_bytes[:4] == _ZIP_MAGIC:
        return "zip"
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "zip":
            return "zip"
        if ext == "txt":
            return "txt"
    return "csv"


def extract_txt_from_zip(file_bytes):
    """ZIP 파일에서 첫 번째 TXT 파일을 추출하여 바이트로 반환한다."""
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
            txt_names = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not txt_names:
                return None, "ZIP 파일 안에 TXT 파일이 없습니다."
            info = zf.getinfo(txt_names[0])
            if info.file_size > MAX_DECOMPRESSED_BYTES:
                return None, f"TXT 파일이 너무 큽니다. (최대 {MAX_DECOMPRESSED_BYTES // (1024 * 1024)}MB)"
            return zf.read(txt_names[0]), None
    except zipfile.BadZipFile:
        return None, "올바른 ZIP 파일이 아닙니다."


def extract_csv_meta(filename):
    """CSV 파일명에서 방 이름과 내보내기 시점을 추출한다.

    Returns:
        tuple: (room_name, saved_date) — 각각 str|None
    """
    if not filename:
        return None, None
    m = _CSV_FILENAME_RE.search(filename)
    if not m:
        return None, None
    room_name = m.group(1)
    saved_date = f"{m.group(2)}/{m.group(3)}/{m.group(4)}-{m.group(5)}:{m.group(6)}"
    return room_name, saved_date


def extract_zip_meta(filename):
    """ZIP 파일명에서 방 이름과 내보내기 시점을 추출한다.

    Returns:
        tuple: (room_name, saved_date) — 각각 str|None
    """
    if not filename:
        return None, None
    m = _ZIP_FILENAME_RE.search(filename)
    if not m:
        return None, None
    room_name = m.group(1)
    saved_date = f"{m.group(2)}/{m.group(3)}/{m.group(4)}-{m.group(5)}:{m.group(6)}"
    return room_name, saved_date


def extract_room_roster(text, normalize_name):
    """대화 원문의 초대·입퇴장 시스템 메시지로 방 멤버 명단을 만든다.

    한 번도 인증하지 않은 멤버를 진도표에 남기기 위한 명단이다.
    normalize_name은 표시 이름에서 실제 이름만 남기는 함수(analyzer.normalize_user_name).
    """
    if not text:
        return []

    joined = set()
    left = set()
    for match in _INVITE_RE.finditer(text):
        # 초대한 사람도 방 멤버다 (부방장이 초대하는 경우가 있다)
        joined.add(match.group(1))
        joined.update(n.strip() for n in _NAME_IN_LIST_RE.findall(match.group(2)))
    for match in _OWNER_RE.finditer(text):
        joined.add(match.group(1))
    for match in _JOIN_RE.finditer(text):
        joined.add(match.group(1))
    for match in _LEAVE_RE.finditer(text):
        left.add(match.group(1))
    for match in _KICK_RE.finditer(text):
        joined.add(match.group(1))
        left.update(n.strip() for n in _NAME_IN_LIST_RE.findall(match.group(2)))

    def cleaned(names):
        result = set()
        for name in names:
            value = normalize_name(name.strip())
            if value:
                result.add(value)
        return result

    roster = sorted(cleaned(joined) - cleaned(left))
    logger.info("방 멤버 명단 추출: %d명", len(roster))
    return roster


def detect_track_mode(rows):
    """투트랙 방 여부를 판별하여 track_mode를 반환한다.

    1) 투트랙 공지 문구가 있으면 dual
    2) 없으면 날짜 인증 메시지 중 "구약"/"신약"을 적은 비율로 판단
       (공지 문구는 기수마다 바뀌지만 인증 형태는 유지된다)
    """
    from app.date_parser import parse_dates

    dated = 0
    with_track = 0
    for _, message in rows:
        if not message:
            continue
        if _DUAL_MARKER in message:
            return "dual"
        if not parse_dates(message):
            continue
        dated += 1
        if any(word in message for word in _DUAL_TRACK_WORDS):
            with_track += 1

    if with_track >= _DUAL_MIN_MESSAGES and with_track >= dated * _DUAL_MIN_RATIO:
        logger.info(
            "투트랙 감지 — 날짜 인증 %d건 중 구약/신약 표기 %d건", dated, with_track,
        )
        return "dual"
    return "single"


_LEADER_STRIP_WORDS = ("맑은샘", "광천", "누나", "오빠", "언니", " 형")


def clean_leader_name(name):
    """방장 이름에서 키워드·영어·공백을 제거하고, 3글자 한글이면 성을 뺀다."""
    cleaned = name
    for word in _LEADER_STRIP_WORDS:
        cleaned = cleaned.replace(word, "")
    cleaned = re.sub(r"[A-Za-z\s]", "", cleaned)
    if not cleaned:
        return name
    if len(cleaned) == 3 and all("\uAC00" <= ch <= "\uD7A3" for ch in cleaned):
        cleaned = cleaned[1:]
    return cleaned


def extract_leader(rows):
    """rows에서 방장(안내 메시지 발신자) 이름을 추출한다."""
    for user, message in rows:
        if _LEADER_KEYWORD in message:
            return clean_leader_name(user)
    return None


def build_drive_filename(leader, saved_date, room_name=None):
    """방장 이름과 저장 날짜로 Drive 업로드용 파일명을 생성한다.

    Args:
        leader: 방장 이름 (None이면 기본값 사용)
        saved_date: "YYYY/MM/DD-HH:MM" 형식 (None이면 기본값 사용)
        room_name: 카톡방 이름 (None이면 기존 형식 유지)

    Returns:
        str|None: "꿀성경_방장_YYYYMMDD_HHMM_방이름.xlsx" 또는 None
    """
    if not leader and not saved_date:
        return None
    name_part = leader or "결과"
    date_part = ""
    if saved_date:
        # "YYYY/MM/DD-HH:MM" → "YYYYMMDD_HHMM"
        date_part = "_" + saved_date.replace("/", "").replace("-", "_").replace(":", "")
    room_part = ""
    if room_name:
        clean_room = re.sub(r'[\\/*?:"<>|]', "", room_name).strip()
        if clean_room:
            room_part = f"_{clean_room}"
    return f"꿀성경_{name_part}{date_part}{room_part}.xlsx"


def detect_schedule_type(rows, room_name, track_mode, part=None):
    """파싱된 행, 방이름, 트랙모드를 기반으로 진도표 유형을 판별한다.

    Returns:
        str: "dual", "education", "bible", "nt", "unknown" 중 하나
    """
    from app.schedule import BIBLE_PART_DATES, NT_PART_DATES, detect_schedule

    if track_mode == "dual":
        return "dual"
    normalized_room_name = unicodedata.normalize("NFC", room_name or "")
    if "교육국" in normalized_room_name:
        return "education"
    schedule = detect_schedule(rows, part=part)
    if schedule is None:
        return "unknown"
    if schedule in BIBLE_PART_DATES:
        return "bible"
    if schedule in NT_PART_DATES:
        return "nt"
    return "unknown"
