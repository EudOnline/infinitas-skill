"""
Search API for infinitas-skill
Provides global search across skills, commands, and documentation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from server.auth import get_current_user, require_registry_reader, require_registry_reader_or_user
from server.settings import get_settings

router = APIRouter(prefix="/api", tags=["search"])


def _pick_lang(lang: str, zh: str, en: str) -> str:
    return en if lang == "en" else zh


class SkillSearchResult(BaseModel):
    id: str
    name: str
    qualified_name: str
    version: str
    summary: str
    icon: str = "🎯"
    tags: List[str] = []
    rating: Optional[float] = None
    status: str = "active"


class CommandSearchResult(BaseModel):
    name: str
    command: str
    description: str
    skill_id: Optional[str] = None


class SearchResponse(BaseModel):
    skills: List[SkillSearchResult]
    commands: List[CommandSearchResult]
    total: int


def _read_json(path: Path) -> dict:
    """Read and parse JSON file"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _calculate_relevance(query: str, text: str) -> float:
    """Calculate relevance score between query and text"""
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Exact match gets highest score
    if query_lower == text_lower:
        return 100.0
    
    # Starts with query
    if text_lower.startswith(query_lower):
        return 80.0
    
    # Contains query
    if query_lower in text_lower:
        return 60.0
    
    # Fuzzy match using SequenceMatcher
    return SequenceMatcher(None, query_lower, text_lower).ratio() * 50


def _search_skills(query: str, catalog_data: dict, limit: int = 5) -> List[SkillSearchResult]:
    """Search skills with relevance scoring"""
    results = []
    
    skills = catalog_data.get("skills", [])
    
    for skill in skills:
        # Calculate relevance score
        score = 0
        
        # Name match (highest weight)
        score += _calculate_relevance(query, skill.get("name", "")) * 2
        
        # Qualified name match
        score += _calculate_relevance(query, skill.get("qualified_name", ""))
        
        # Summary match
        score += _calculate_relevance(query, skill.get("summary", "")) * 0.5
        
        # Tag matches
        for tag in skill.get("tags", []):
            if query.lower() in tag.lower():
                score += 30
        
        # Author match
        score += _calculate_relevance(query, skill.get("author", "")) * 0.3
        
        if score > 10:  # Threshold
            # Determine emoji icon based on tags/name
            icon = _get_skill_icon(skill)
            
            results.append({
                "skill": SkillSearchResult(
                    id=skill.get("name", ""),
                    name=skill.get("name", ""),
                    qualified_name=skill.get("qualified_name", ""),
                    version=skill.get("version", ""),
                    summary=skill.get("summary", "")[:100] + "..." if len(skill.get("summary", "")) > 100 else skill.get("summary", ""),
                    icon=icon,
                    tags=skill.get("tags", [])[:3],
                    rating=_calculate_rating(skill),
                    status=skill.get("status", "active")
                ),
                "score": score
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return [r["skill"] for r in results[:limit]]


def _get_skill_icon(skill: dict) -> str:
    """Get emoji icon based on skill tags/name"""
    name = skill.get("name", "").lower()
    tags = [t.lower() for t in skill.get("tags", [])]
    
    # Tag-based icons
    if "discovery" in tags or "search" in tags:
        return "🔍"
    if "install" in tags or "pull" in tags:
        return "📦"
    if "release" in tags or "publish" in tags:
        return "🚀"
    if "operate" in tags or "manage" in tags:
        return "🔧"
    if "security" in tags or "check" in tags:
        return "🔒"
    if "test" in tags:
        return "🧪"
    if "build" in tags or "catalog" in tags:
        return "📊"
    
    # Name-based icons
    if "consume" in name:
        return "🎯"
    if "operate" in name:
        return "🔧"
    if "release" in name:
        return "🚀"
    if "federation" in name:
        return "🌐"
    
    return "🎯"


def _calculate_rating(skill: dict) -> Optional[float]:
    """Calculate skill rating based on review state"""
    review_state = skill.get("review_state", "")
    approval_count = skill.get("approval_count", 0)
    
    if review_state == "approved" and approval_count > 0:
        # Base rating on approvals
        base = 4.5
        if approval_count >= 2:
            base = 4.8
        return round(base, 1)
    
    return None


def _search_commands(query: str, limit: int = 3, lang: str = "zh") -> List[CommandSearchResult]:
    """Search common commands"""
    commands = [
        CommandSearchResult(
            name=_pick_lang(lang, "搜索技能", "Search skills"),
            command='scripts/search-skills.sh "keyword"',
            description=_pick_lang(lang, "从发现索引搜索技能", "Search skills from the discovery index"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "推荐技能", "Recommend skill"),
            command='scripts/recommend-skill.sh "task description"',
            description=_pick_lang(lang, "根据任务描述推荐最佳技能", "Recommend the best skill for a task"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "检查技能", "Inspect skill"),
            command='scripts/inspect-skill.sh publisher/skill-name',
            description=_pick_lang(lang, "检查技能的信任状态和兼容性", "Inspect trust state and compatibility"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "安装技能", "Install skill"),
            command='scripts/install-by-name.sh skill-name',
            description=_pick_lang(lang, "通过名称安装技能", "Install a skill by name"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "拉取技能", "Pull skill"),
            command='scripts/pull-skill.sh publisher/skill/version',
            description=_pick_lang(lang, "从不可变工件拉取技能", "Pull a skill from immutable artifacts"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "检查更新", "Check updates"),
            command='scripts/check-skill-update.sh skill-name',
            description=_pick_lang(lang, "检查技能是否有新版本", "Check whether a skill has a newer version"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "升级技能", "Upgrade skill"),
            command='scripts/upgrade-skill.sh skill-name',
            description=_pick_lang(lang, "升级已安装的技能", "Upgrade an installed skill"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "构建目录", "Build catalog"),
            command='scripts/build-catalog.sh',
            description=_pick_lang(lang, "重新生成技能目录索引", "Rebuild the catalog index"),
        ),
        CommandSearchResult(
            name=_pick_lang(lang, "验证技能", "Validate skill"),
            command='scripts/check-skill.sh skills/active/skill-name',
            description=_pick_lang(lang, "验证技能元数据和结构", "Validate skill metadata and structure"),
        ),
    ]
    
    results = []
    query_lower = query.lower()
    
    for cmd in commands:
        score = 0
        
        # Name match
        if query_lower in cmd.name.lower():
            score += 50
        
        # Command match
        if query_lower in cmd.command.lower():
            score += 30
        
        # Description match
        if query_lower in cmd.description.lower():
            score += 20
        
        if score > 0:
            results.append({"cmd": cmd, "score": score})
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return [r["cmd"] for r in results[:limit]]


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=100, description="Search query"),
    limit: int = Query(default=5, ge=1, le=10, description="Max results per category"),
    lang: str = Query(default="zh", description="UI language"),
    _: None = Depends(require_registry_reader_or_user),
):
    """
    Global search across skills and commands
    
    - Skills are matched by name, summary, tags, and author
    - Commands are matched by name and description
    - Results are ranked by relevance
    """
    settings = get_settings()
    
    # Load catalog
    catalog_path = settings.root_dir / "catalog" / "catalog.json"
    catalog_data = _read_json(catalog_path)
    
    # Search skills
    skills = _search_skills(q, catalog_data, limit)
    
    # Search commands
    commands = _search_commands(q, limit, "en" if lang.startswith("en") else "zh")
    
    return SearchResponse(
        skills=skills,
        commands=commands,
        total=len(skills) + len(commands)
    )


@router.get("/skills/{skill_id}", response_model=SkillSearchResult)
async def get_skill_detail(
    skill_id: str,
    _: None = Depends(require_registry_reader_or_user),
):
    """Get detailed information about a specific skill"""
    settings = get_settings()
    
    catalog_path = settings.root_dir / "catalog" / "catalog.json"
    catalog_data = _read_json(catalog_path)
    
    for skill in catalog_data.get("skills", []):
        if skill.get("name") == skill_id or skill.get("qualified_name") == skill_id:
            return SkillSearchResult(
                id=skill.get("name", ""),
                name=skill.get("name", ""),
                qualified_name=skill.get("qualified_name", ""),
                version=skill.get("version", ""),
                summary=skill.get("summary", ""),
                icon=_get_skill_icon(skill),
                tags=skill.get("tags", []),
                rating=_calculate_rating(skill),
                status=skill.get("status", "active")
            )
    
    raise HTTPException(status_code=404, detail="Skill not found")


@router.post("/skills/{skill_id}/use")
async def use_skill(
    skill_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Record skill usage and return installation command
    
    This endpoint:
    1. Records the usage for analytics
    2. Returns the appropriate command for the skill
    """
    settings = get_settings()
    
    # Load skill info
    catalog_path = settings.root_dir / "catalog" / "catalog.json"
    catalog_data = _read_json(catalog_path)
    
    skill = None
    for s in catalog_data.get("skills", []):
        if s.get("name") == skill_id:
            skill = s
            break
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    # Generate command
    qualified_name = skill.get("qualified_name", skill.get("name"))
    command = f"scripts/install-skill.sh {qualified_name}"
    
    # TODO: Record usage analytics
    # This would typically write to a database
    
    return {
        "command": command,
        "skill": {
            "id": skill.get("name"),
            "name": skill.get("name"),
            "qualified_name": qualified_name,
            "version": skill.get("version")
        }
    }
