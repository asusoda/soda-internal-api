import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from modules.marketing.models import MarketingEvent, MarketingConfig, MarketingLog
from modules.marketing.events import get_upcoming_events
from modules.marketing.claude import generate_content, generate_grapes_code
from modules.marketing.message import send_officer_notification
from modules.marketing.selenium import post_to_social_media
from shared import db_connect


class MarketingService:
    """
    Service class for managing marketing automation functionality
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.db_connect = db_connect
        
    def get_all_events(self) -> List[Dict]:
        """Get all marketing events from the database"""
        db = next(self.db_connect.get_db())
        try:
            events = db.query(MarketingEvent).order_by(MarketingEvent.created_at.desc()).all()
            return [event.to_dict() for event in events]
        except Exception as e:
            self.logger.error(f"Error fetching marketing events: {e}")
            return []
        finally:
            db.close()
    
    def get_event_by_id(self, event_id: str) -> Optional[Dict]:
        """Get a specific marketing event by ID"""
        db = next(self.db_connect.get_db())
        try:
            event = db.query(MarketingEvent).filter(MarketingEvent.event_id == event_id).first()
            return event.to_dict() if event else None
        except Exception as e:
            self.logger.error(f"Error fetching event {event_id}: {e}")
            return None
        finally:
            db.close()
    
    def save_event(self, event_data: Dict) -> bool:
        """Save or update a marketing event"""
        db = next(self.db_connect.get_db())
        try:
            # Check if event already exists
            existing_event = db.query(MarketingEvent).filter(
                MarketingEvent.event_id == event_data['event_id']
            ).first()
            
            if existing_event:
                # Update existing event
                for key, value in event_data.items():
                    if key == 'grapes_code':
                        existing_event.html = value.get('html', '')
                        existing_event.css = value.get('css', '')
                    elif hasattr(existing_event, key):
                        setattr(existing_event, key, value)
                existing_event.updated_at = datetime.utcnow()
            else:
                # Create new event
                grapes_code = event_data.pop('grapes_code', {})
                new_event = MarketingEvent(
                    **event_data,
                    html=grapes_code.get('html', ''),
                    css=grapes_code.get('css', '')
                )
                db.add(new_event)
            
            db.commit()
            self.logger.info(f"Saved marketing event: {event_data['event_id']}")
            return True
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error saving event: {e}")
            return False
        finally:
            db.close()
    
    def mark_event_completed(self, event_id: str) -> bool:
        """Mark an event as completed"""
        db = next(self.db_connect.get_db())
        try:
            event = db.query(MarketingEvent).filter(MarketingEvent.event_id == event_id).first()
            if event:
                event.is_completed = True
                event.status = 'completed'
                event.completed_at = datetime.utcnow()
                event.updated_at = datetime.utcnow()
                db.commit()
                self.logger.info(f"Marked event {event_id} as completed")
                return True
            return False
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error marking event completed: {e}")
            return False
        finally:
            db.close()
    
    def get_completed_events(self) -> List[Dict]:
        """Get all completed marketing events"""
        db = next(self.db_connect.get_db())
        try:
            events = db.query(MarketingEvent).filter(
                MarketingEvent.is_completed == True
            ).order_by(MarketingEvent.completed_at.desc()).all()
            return [event.to_dict() for event in events]
        except Exception as e:
            self.logger.error(f"Error fetching completed events: {e}")
            return []
        finally:
            db.close()
    
    def log_activity(self, event_id: str, action: str, status: str, platform: str = None, 
                    message: str = None, metadata: Dict = None) -> bool:
        """Log marketing activity"""
        db = next(self.db_connect.get_db())
        try:
            log_entry = MarketingLog(
                event_id=event_id,
                action=action,
                platform=platform,
                status=status,
                message=message,
                metadata=metadata
            )
            db.add(log_entry)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error logging activity: {e}")
            return False
        finally:
            db.close()
    
    def get_config(self, key: str) -> Optional[str]:
        """Get a configuration value"""
        db = next(self.db_connect.get_db())
        try:
            config_item = db.query(MarketingConfig).filter(MarketingConfig.key == key).first()
            return config_item.value if config_item else None
        except Exception as e:
            self.logger.error(f"Error fetching config {key}: {e}")
            return None
        finally:
            db.close()
    
    def set_config(self, key: str, value: str, description: str = None) -> bool:
        """Set a configuration value"""
        db = next(self.db_connect.get_db())
        try:
            config_item = db.query(MarketingConfig).filter(MarketingConfig.key == key).first()
            if config_item:
                config_item.value = value
                config_item.updated_at = datetime.utcnow()
                if description:
                    config_item.description = description
            else:
                config_item = MarketingConfig(key=key, value=value, description=description)
                db.add(config_item)
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            self.logger.error(f"Error setting config {key}: {e}")
            return False
        finally:
            db.close()
    
    def monitor_events(self) -> None:
        """Monitor for upcoming events and generate content"""
        self.logger.info("Starting event monitoring...")
        
        try:
            # Get upcoming events from the calendar API
            upcoming_events = get_upcoming_events()
            
            for event_data in upcoming_events:
                event_id = event_data.get('id')
                
                # Check if we already have this event
                existing_event = self.get_event_by_id(event_id)
                if existing_event:
                    self.logger.debug(f"Event {event_id} already exists, skipping")
                    continue
                
                self.logger.info(f"Processing new event: {event_id}")
                
                # Save the basic event data
                event_info = {
                    'event_id': event_id,
                    'name': event_data.get('name', ''),
                    'date': datetime.fromisoformat(event_data['date']) if event_data.get('date') else None,
                    'location': event_data.get('location', ''),
                    'info': event_data.get('info', ''),
                    'status': 'pending'
                }
                
                if self.save_event(event_info):
                    # Generate content for the event
                    self.generate_event_content(event_id, event_data)
                    
                    # Send notification to officers
                    try:
                        send_officer_notification(event_data)
                        self.log_activity(event_id, 'send_notification', 'success', 'discord')
                    except Exception as e:
                        self.logger.error(f"Failed to send notification for {event_id}: {e}")
                        self.log_activity(event_id, 'send_notification', 'failed', 'discord', str(e))
                        
        except Exception as e:
            self.logger.error(f"Error in event monitoring: {e}")
    
    def generate_event_content(self, event_id: str, event_data: Dict) -> bool:
        """Generate marketing content for an event"""
        try:
            self.logger.info(f"Generating content for event {event_id}")
            
            # Generate text content using Claude
            content = generate_content(event_data)
            
            # Generate visual content (GrapesJS code)
            grapes_code = generate_grapes_code(event_data)
            
            # Update the event with generated content
            update_data = {
                'event_id': event_id,
                'content': content,
                'grapes_code': grapes_code,
                'status': 'content_generated'
            }
            
            success = self.save_event(update_data)
            
            if success:
                self.log_activity(event_id, 'generate_content', 'success')
                self.logger.info(f"Successfully generated content for event {event_id}")
            else:
                self.log_activity(event_id, 'generate_content', 'failed')
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error generating content for event {event_id}: {e}")
            self.log_activity(event_id, 'generate_content', 'failed', message=str(e))
            return False
    
    def post_to_social_media(self, event_id: str, platforms: List[str] = None) -> bool:
        """Post event content to social media platforms"""
        try:
            event = self.get_event_by_id(event_id)
            if not event:
                self.logger.error(f"Event {event_id} not found")
                return False
            
            if not event.get('content'):
                self.logger.error(f"No content available for event {event_id}")
                return False
            
            platforms = platforms or ['instagram', 'linkedin']
            success = True
            
            for platform in platforms:
                try:
                    platform_content = event['content'].get(platform, {})
                    if platform_content:
                        post_to_social_media(platform, platform_content, event_id)
                        self.log_activity(event_id, 'post_social', 'success', platform)
                        self.logger.info(f"Posted to {platform} for event {event_id}")
                    else:
                        self.logger.warning(f"No content for {platform} for event {event_id}")
                        
                except Exception as e:
                    self.logger.error(f"Failed to post to {platform} for event {event_id}: {e}")
                    self.log_activity(event_id, 'post_social', 'failed', platform, str(e))
                    success = False
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error posting to social media for event {event_id}: {e}")
            return False
