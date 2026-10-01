"""Auth layer ของ Nova Studio — thin wrapper รอบ cloudforge-auth-core
Studio ไม่ควรมี local token (ไม่ควรมี create_access_token)
ไม่ควร implement JWT verify / scope parse เอง
"""
from src.auth.dependencies import Principal, get_current_user, require_scope

require_nova_query = require_scope("nova:query")

__all__ = ["get_current_user", "require_nova_query", "Principal"]
