"""
Database Table Verification Utility

Checks that all SQLAlchemy models have corresponding tables in the database.
Automatically creates missing tables to prevent runtime errors.
"""
import logging
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)


def verify_and_create_tables(db, app):
    """
    Verify all model tables exist in the database.
    Creates missing tables automatically.
    
    Returns a list of tables that were created.
    """
    created_tables = []
    missing_tables = []
    
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        
        # Get all model table names from metadata
        model_tables = set(db.metadata.tables.keys())
        
        # Find missing tables
        missing_tables = model_tables - existing_tables
        
        if missing_tables:
            logger.warning(f"Missing database tables detected: {missing_tables}")
            
            # Create only the missing tables
            for table_name in missing_tables:
                table = db.metadata.tables.get(table_name)
                if table is not None:
                    try:
                        table.create(db.engine, checkfirst=True)
                        created_tables.append(table_name)
                        logger.info(f"Created missing table: {table_name}")
                    except Exception as e:
                        logger.error(f"Failed to create table {table_name}: {e}")
        
        if created_tables:
            logger.info(f"Database verification complete. Created {len(created_tables)} missing tables: {created_tables}")
        else:
            logger.debug("Database verification complete. All tables exist.")
    
    return created_tables


def get_table_status(db, app):
    """
    Get detailed status of all model tables.
    
    Returns dict with 'existing', 'missing', and 'extra' table lists.
    """
    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        model_tables = set(db.metadata.tables.keys())
        
        return {
            'existing': list(model_tables & existing_tables),
            'missing': list(model_tables - existing_tables),
            'extra': list(existing_tables - model_tables),
            'total_models': len(model_tables),
            'total_db_tables': len(existing_tables)
        }
