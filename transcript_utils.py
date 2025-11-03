# project_root/transcript_utils.py
import re

def cleanup_transcript(text: str) -> str:
    if not text:
        return ""
    # Simple cleaning: strip extra whitespace, remove repeated punctuation, limit length
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"([.?!]){2,}", r"\1", t)
    if len(t) > 5000:
        t = t[:5000] + "..."
    return t
