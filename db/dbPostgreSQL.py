import psycopg2
from psycopg2.extras import RealDictCursor
from pathlib import Path
from typing import List, Dict, Optional, Any
import json
import os

import sys
import os
# Add parent directory to path to import db module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logging_config import setup_logger

class BaseDB:
    """공통 데이터베이스 연결 및 테이블 생성 관리"""
    
    def __init__(self, host: str = "localhost", port: int = 5432, database: str = "notice_db", 
                 user: str = "postgres", password: str = "password"):
        """PostgreSQL database initialization"""
        self.main_logger = setup_logger()
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.conn = self._config_data_based()
    
    def __del__(self):
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
        except Exception:
            # PostgreSQL 연결 오류는 무시 (프로그램 종료 시 발생 가능)
            pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, 'conn') and self.conn:
            if exc_type is not None:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.conn.close()
    
    
    def _config_data_based(self):
        """PostgreSQL database connection and table creation"""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                cursor_factory=RealDictCursor
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            # main.notificationList table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notificationList (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    login INTEGER NOT NULL DEFAULT 0,
                    display_type TEXT DEFAULT 'button',
                    college TEXT DEFAULT NULL,
                    department TEXT DEFAULT NULL,
                    major TEXT DEFAULT NULL,
                    description TEXT DEFAULT NULL,
                    link_selector TEXT DEFAULT NULL,
                    content_selector TEXT DEFAULT NULL
                )
            ''')
            
            # User table for website
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS "user" (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    subscribe TEXT DEFAULT '',
                    email_notifications BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # User subscriptions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    user_id TEXT NOT NULL,
                    notification_id INTEGER NOT NULL,
                    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    PRIMARY KEY (user_id, notification_id),
                    FOREIGN KEY (user_id) REFERENCES "user"(id) ON DELETE CASCADE,
                    FOREIGN KEY (notification_id) REFERENCES notificationList(id) ON DELETE CASCADE
                )
            ''')
            
            # Email sending log table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_log (
                    id SERIAL PRIMARY KEY,
                    notification_id INTEGER NOT NULL,
                    sent_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    recipient_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT DEFAULT NULL,
                    FOREIGN KEY (notification_id) REFERENCES notificationList(id)
                )
            ''')
            
            return conn
        except psycopg2.Error as e:
            self.main_logger.error(f"PostgreSQL connection failed: {e}")
            raise
    
    def _create_notification_data_table(self, notification_id, cursor=None):
        if cursor is None:
            cursor = self.conn.cursor()
        
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS notification_data_{notification_id} (
                id SERIAL PRIMARY KEY,
                link TEXT NOT NULL,
                crawl_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                title TEXT NOT NULL,
                raw_html TEXT,
                ai_json_data TEXT
            )
        ''')

class CrawlerDB(BaseDB):
    """크롤링 관련 데이터베이스 작업"""
    
    def save_program_to_db(self, notification_id, program: Dict[str, Any]):
        """Save program info to PostgreSQL database"""
        cursor = self.conn.cursor()
        
        self._create_notification_data_table(notification_id, cursor)
        try:
            cursor.execute(f'''
                    INSERT INTO notification_data_{notification_id} 
                    (link, crawl_timestamp, title, raw_html, ai_json_data) 
                    VALUES (%s, %s, %s, %s, %s)
            ''', (
                program.get('program_link'),
                program.get('crawl_timestamp', None),
                program.get('title', None),
                program.get('raw_html', None),
                json.dumps(program.get('ai_json_data', None), ensure_ascii=False, indent=2) if isinstance(program.get('ai_json_data', None), dict) else str(program.get('ai_json_data', None))
            ))
            return {"code": 1}
        except Exception as e:
            self.main_logger.error(f"Save program to DB failed: {e}")
            return {"code": -1}
    
    def get_existing_links(self, notification_id: int) -> set:
        """Get existing crawled links from DB"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
            """, (f'notification_data_{notification_id}',))
            if not cursor.fetchone():
                return set()
            
            cursor.execute(f'SELECT link FROM notification_data_{notification_id}')
            existing_links = cursor.fetchall()
            return {link['link'] for link in existing_links}
            
        except Exception as e:
            self.main_logger.error(f"Get existing links failed (notification_id: {notification_id}): {e}")
            return set()
    
    def get_notification_info(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Get notification info from notificationList"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT title, url, link_selector, content_selector 
                FROM notificationList 
                WHERE id = %s
            ''', (notification_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'title': result['title'],
                    'url': result['url'], 
                    'link_selector': result['link_selector'],
                    'content_selector': result['content_selector']
                }
            return None
            
        except Exception as e:
            self.main_logger.error(f"Get notification info failed (notification_id: {notification_id}): {e}")
            return None

    def get_all_ids(self) -> List[int]:
        """Return all notification IDs"""
        cursor = self.conn.cursor()
        
        try:
            # Get all notification IDs
            cursor.execute('SELECT id FROM notificationList ORDER BY id')
            notification_ids = [row['id'] for row in cursor.fetchall()]
            
            return notification_ids
            
        except Exception as e:
            self.main_logger.error(f"Get all notification IDs failed: {e}")
            return []

class WebsiteDB(BaseDB):
    """웹사이트 관련 데이터베이스 작업"""
    def update_user_subscriptions(self, user_id: str, notification_ids: List[int]) -> Dict[str, Any]:
        """사용자의 구독 목록을 일괄 업데이트"""
        cursor = self.conn.cursor()
        
        try:
            # 기존 구독을 모두 비활성화
            cursor.execute('''
                UPDATE user_subscriptions 
                SET is_active = FALSE 
                WHERE user_id = %s
            ''', (user_id,))
            
            # 새로운 구독 목록 추가/활성화
            for notification_id in notification_ids:
                cursor.execute('''
                    INSERT INTO user_subscriptions 
                    (user_id, notification_id, is_active, subscribed_at)
                    VALUES (%s, %s, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, notification_id) 
                    DO UPDATE SET is_active = TRUE, subscribed_at = CURRENT_TIMESTAMP
                ''', (user_id, notification_id))
            
            return {"code": 1, "message": f"{len(notification_ids)}개 구독 업데이트 완료"}
        except Exception as e:
            self.main_logger.error(f"구독 업데이트 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """구독 통계 조회"""
        cursor = self.conn.cursor()
        
        try:
            # 전체 구독 수
            cursor.execute('SELECT COUNT(*) as count FROM user_subscriptions WHERE is_active = TRUE')
            total_subscriptions = cursor.fetchone()['count']
            
            # 공지사항별 구독자 수
            cursor.execute('''
                SELECT nl.title, COUNT(us.user_id) as subscriber_count
                FROM notificationList nl
                LEFT JOIN user_subscriptions us ON nl.id = us.notification_id AND us.is_active = TRUE
                GROUP BY nl.id, nl.title
                ORDER BY subscriber_count DESC
            ''')
            
            notification_stats = []
            for row in cursor.fetchall():
                notification_stats.append({
                    'title': row['title'],
                    'subscriber_count': row['subscriber_count']
                })
            
            return {
                'total_subscriptions': total_subscriptions,
                'notification_stats': notification_stats
            }
        except Exception as e:
            self.main_logger.error(f"통계 조회 실패: {e}")
            return {'total_subscriptions': 0, 'notification_stats': []}
    
    def get_user_subscription_ids(self, user_id: str) -> List[int]:
        """사용자의 구독 ID 목록만 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT notification_id 
                FROM user_subscriptions 
                WHERE user_id = %s AND is_active = TRUE
            ''', (user_id,))
            
            return [row['notification_id'] for row in cursor.fetchall()]
        except Exception as e:
            self.main_logger.error(f"구독 ID 목록 조회 실패: {e}")
            return []
    
    def get_notification_categories(self):
        """공지사항 카테고리 데이터 조회 (버튼 및 드롭다운)"""
        cursor = self.conn.cursor()
        
        try:
            # 버튼 방식 공지사항
            cursor.execute('''
                SELECT id, title, url, display_type, description
                FROM notificationList 
                WHERE display_type = %s 
                ORDER BY id
            ''', ('button',))
            button_notifications = cursor.fetchall()
            
            # 드롭다운 방식 공지사항
            cursor.execute('''
                SELECT id, title, url, college, department, major
                FROM notificationList 
                WHERE display_type = %s 
                ORDER BY college, department, major
            ''', ('dropdown',))
            dropdown_notifications = cursor.fetchall()
            
            # 드롭다운 데이터 구조화
            dropdown_data = {}
            for row in dropdown_notifications:
                id = row['id']
                title = row['title']
                url = row['url']
                college = row['college']
                department = row['department']
                major = row['major']
                
                if college not in dropdown_data:
                    dropdown_data[college] = {}
                
                if department not in dropdown_data[college]:
                    dropdown_data[college][department] = []
                
                dropdown_data[college][department].append({
                    'id': id,
                    'title': title,
                    'url': url,
                    'major': major
                })
            
            return button_notifications, dropdown_data
        except Exception as e:
            self.main_logger.error(f"카테고리 데이터 조회 실패: {e}")
            return [], {}
    
    def get_user_notifications(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """사용자의 구독 공지사항 데이터 조회"""
        cursor = self.conn.cursor()
        subscribed_ids = self.get_user_subscription_ids(user_id)
        
        if not subscribed_ids:
            return []
        
        notifications = []
        
        try:
            for sub_id in subscribed_ids:
                # 테이블이 존재하는지 확인
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = %s
                """, (f'notification_data_{sub_id}',))
                if not cursor.fetchone():
                    self._create_notification_data_table(sub_id)
                    continue
                
                try:
                    cursor.execute(f'''
                        SELECT nd.title, nd.link, nd.crawl_timestamp, nl.title as category, nl.display_type
                        FROM notification_data_{sub_id} nd
                        JOIN notificationList nl ON nl.id = %s
                        ORDER BY nd.crawl_timestamp DESC
                        LIMIT 10
                    ''', (sub_id,))
                    
                    for row in cursor.fetchall():
                        notifications.append({
                            'title': row['title'],
                            'link': row['link'],
                            'timestamp': row['crawl_timestamp'],
                            'category': row['category'],
                            'display_type': row['display_type']
                        })
                except Exception as table_error:
                    self.main_logger.error(f"테이블 {sub_id} 조회 오류: {table_error}")
                    continue
            
            # 시간순 정렬 후 페이지네이션 (None 값 처리)
            notifications.sort(key=lambda x: x.get('timestamp') or '1970-01-01 00:00:00', reverse=True)
            return notifications[offset:offset + limit]
            
        except Exception as e:
            self.main_logger.error(f"사용자 공지사항 조회 실패: {e}")
            return []
    
    def register_user(self, user_id: str, email: str) -> Dict[str, Any]:
        """사용자 등록/업데이트"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO "user" (id, email, subscribe, email_notifications) 
                VALUES (%s, %s, 
                    COALESCE((SELECT subscribe FROM "user" WHERE id = %s), ''),
                    COALESCE((SELECT email_notifications FROM "user" WHERE id = %s), TRUE))
                ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
            ''', (user_id, email, user_id, user_id))
            return {"code": 1, "message": "사용자 등록 성공"}
        except Exception as e:
            self.main_logger.error(f"사용자 등록 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def delete_user(self, user_id: str) -> Dict[str, Any]:
        """사용자 삭제"""
        cursor = self.conn.cursor()
        
        try:
            # 사용자 구독 데이터 먼저 삭제 (CASCADE로 자동 삭제되지만 명시적으로)
            cursor.execute('DELETE FROM user_subscriptions WHERE user_id = %s', (user_id,))
            
            # 사용자 데이터 삭제
            cursor.execute('DELETE FROM "user" WHERE id = %s', (user_id,))
            
            if cursor.rowcount == 0:
                return {"code": -1, "message": "사용자를 찾을 수 없습니다"}
            
            return {"code": 1, "message": "사용자 삭제 성공"}
        except Exception as e:
            self.main_logger.error(f"사용자 삭제 실패: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_user_email_notifications(self, user_id: str) -> bool:
        """사용자의 이메일 알림 설정 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('SELECT email_notifications FROM "user" WHERE id = %s', (user_id,))
            result = cursor.fetchone()
            return bool(result['email_notifications']) if result else True  # 기본값은 True
        except Exception as e:
            self.main_logger.error(f"이메일 알림 설정 조회 실패: {e}")
            return True  # 오류 시 기본값 True
    
    def update_user_email_notifications(self, user_id: str, enabled: bool) -> Dict[str, Any]:
        """사용자의 이메일 알림 설정 업데이트"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('UPDATE "user" SET email_notifications = %s WHERE id = %s', (enabled, user_id))
            
            if cursor.rowcount == 0:
                return {"code": -1, "message": "사용자를 찾을 수 없습니다"}
            
            return {"code": 1, "message": "이메일 알림 설정이 업데이트되었습니다"}
        except Exception as e:
            self.main_logger.error(f"이메일 알림 설정 업데이트 실패: {e}")
            return {"code": -1, "message": str(e)}

class EmailDB(BaseDB):
    def log_email_send(self, notification_id: int, recipient_count: int, status: str = 'success', error_message: str = None) -> Dict[str, Any]:
        """Save email sending log"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO email_log (notification_id, recipient_count, status, error_message)
                VALUES (%s, %s, %s, %s)
            ''', (notification_id, recipient_count, status, error_message))
            
            return {"code": 1, "message": "Email send log saved successfully"}
        except Exception as e:
            self.main_logger.error(f"Save email send log failed: {e}")
            return {"code": -1, "message": str(e)}
    
    def get_email_stats(self, days: int = 7) -> Dict[str, Any]:
        """Email sending statistics"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_sends,
                    SUM(recipient_count) as total_recipients,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_sends,
                    COUNT(CASE WHEN status = 'error' THEN 1 END) as failed_sends
                FROM email_log
                WHERE sent_timestamp >= NOW() - INTERVAL '%s days'
            ''', (days,))
            
            result = cursor.fetchone()
            
            return {
                'total_sends': result['total_sends'] or 0,
                'total_recipients': result['total_recipients'] or 0,
                'successful_sends': result['successful_sends'] or 0,
                'failed_sends': result['failed_sends'] or 0,
                'success_rate': (result['successful_sends'] / result['total_sends'] * 100) if result['total_sends'] > 0 else 0
            }
            
        except Exception as e:
            self.main_logger.error(f"Email stats query failed: {e}")
            return {
                'total_sends': 0,
                'total_recipients': 0,
                'successful_sends': 0,
                'failed_sends': 0,
                'success_rate': 0
            }

    def get_all_subscribers_email_initial(self) -> Dict[str, List[int]]:
        """특정 공지사항의 구독자 목록 조회"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT us.notification_id, u.email
                FROM user_subscriptions us
                JOIN "user" u ON us.user_id = u.id
                WHERE us.is_active = TRUE and u.email_notifications = TRUE
                ORDER BY us.notification_id, u.email
            ''')
            
            results = cursor.fetchall()
            
            # Group by email address
            notification_dict = {}
            for row in results:
                notification_id = row['notification_id']
                email = row['email']
                if notification_id not in notification_dict:
                    notification_dict[notification_id] = []
                notification_dict[notification_id].append(email)
            
            return notification_dict
        except Exception as e:
            self.main_logger.error(f"구독자 목록 조회 실패: {e}")
            return {}

    def get_all_subscribers_email_second(self) -> List[Dict[str, Any]]:
        """모든 구독자 목록 조회 [{'email_address': 'joshuayoodevelop@gmail.com', 'notification_ids': [3, 4, 6]}]"""
        cursor = self.conn.cursor()
        
        try:
            cursor.execute('''
                SELECT u.email, us.notification_id
                FROM user_subscriptions us
                JOIN "user" u ON us.user_id = u.id
                WHERE us.is_active = TRUE and u.email_notifications = TRUE
                ORDER BY u.email, us.notification_id
            ''')
            
            results = cursor.fetchall()
            
            # Group by email address
            email_dict = {}
            for row in results:
                email = row['email']
                notification_id = row['notification_id']
                if email not in email_dict:
                    email_dict[email] = []
                email_dict[email].append(notification_id)
            
            # Convert to required format
            subscribers = []
            for email, notification_ids in email_dict.items():
                subscribers.append({
                    "email_address": email,
                    "notification_ids": notification_ids
                })
            
            return subscribers
        except Exception as e:
            self.main_logger.error(f"모든 구독자 목록 조회 실패: {e}")
            return []