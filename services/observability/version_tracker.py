"""Track agent MD file versions via content hashing."""
import hashlib
from pathlib import Path


def compute_prompt_hash(content: str) -> str:
    """SHA-256 hash of agent prompt content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def load_agent_prompt(md_file_path: str) -> str:
    """Load agent prompt from MD file."""
    path = Path(md_file_path)
    if not path.exists():
        raise FileNotFoundError(f"Agent MD file not found: {md_file_path}")
    return path.read_text(encoding="utf-8")


def get_version_info(md_file_path: str) -> dict:
    """Get version info for an agent MD file.

    Returns dict with: prompt, prompt_hash, md_file_path
    """
    content = load_agent_prompt(md_file_path)
    return {
        "prompt": content,
        "prompt_hash": compute_prompt_hash(content),
        "md_file_path": md_file_path,
    }
