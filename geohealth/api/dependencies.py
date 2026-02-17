from geohealth.db.session import get_session

# Re-export for convenient imports in route modules
get_db = get_session
