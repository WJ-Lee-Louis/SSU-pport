import os
import sys
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()
from db.db import EmailDB
from utils.logging_config import setup_logger
from tools.calendar_tool import build_gcal_urls

class EmailSender:
    def __init__(self):
        self.logger = setup_logger()
        self.sender_email = os.getenv('EMAIL_ADDRESS')
        self.password = os.getenv('EMAIL_PASSWORD')

    def _send_email(self, receiver_emails: list, data: dict):
        try:
            # 환경변수에 앱 비밀번호(2단계 인증) 등록 필요
            sender_email = self.sender_email
            password = self.password
        
            category = data.get('category', 'Unknown Category')
            ai_summary = data.get('ai_summary', {}).get('data', {})

            # 안전한 데이터 접근
            if isinstance(ai_summary, str):
                import json
                try:
                    ai_summary = json.loads(ai_summary)
                except json.JSONDecodeError:
                    ai_summary = {}
            
            title = ai_summary.get('title', '')
            schedule = ai_summary.get('schedule', '')
            target = ai_summary.get('target', '')
            application_method = ai_summary.get('application_method', '')
            important_notes = ai_summary.get('summary', '')

            # HTML 템플릿 파일 읽기
            template_path = Path(__file__).parent / 'templates' / 'email_template.html'
            
            html_template = None
            try:
                with open(template_path, 'r', encoding='utf-8') as file:
                    html_template = file.read()
            except FileNotFoundError:
                self.logger.warning(f"템플릿 파일을 찾을 수 없습니다. 평문 이메일로 발송합니다: {template_path}")
            
            # 조건부 섹션 생성 - 주요일정 처리
            schedule_section = ''
            if schedule:
                schedule_html = '<div class="info-item"><span class="info-label">📅 주요일정:</span><div class="schedule-list">'
                
                schedule_data = build_gcal_urls(ai_summary)
                print(schedule_data)  # 디버깅용 출력
                
                # 각 일정 항목을 HTML로 변환
                for item in schedule_data:
                    description = item.get('description', '')
                    date = item.get('date', '')
                    location = item.get('location', '')
                    url = item.get('url', '')

                    # URL이 있으면 <a> 태그로 감싸기
                    if url:
                        schedule_html += f'<a href="{url}" target="_blank" style="text-decoration: none; color: inherit; display: block;">'
                        schedule_html += f'<div class="schedule-item" style="cursor: pointer; padding: 10px; border: 1px solid #ddd; margin-bottom: 8px; border-radius: 4px;">'
                    else:
                        schedule_html += f'<div class="schedule-item" style="padding: 10px; border: 1px solid #ddd; margin-bottom: 8px; border-radius: 4px;">'
                    
                    if description:
                        schedule_html += f'<span class="schedule-desc" style="display: block; font-weight: bold;">📌 {description}</span>'
                    if date:
                        schedule_html += f'<span class="schedule-date" style="display: block; color: #666;">📅 {date}</span>'
                    if location:
                        schedule_html += f'<span class="schedule-location" style="display: block; color: #666;">📍 {location}</span>'
                    
                    schedule_html += f'</div>'
                    
                    if url:
                        schedule_html += f'</a>'

                schedule_html += '</div></div>'
                schedule_section = schedule_html
            
            application_method_section = f'''<div class="info-item">
                <span class="info-label">📝 신청방법:</span>
                <span class="info-value">{application_method}</span>
            </div>''' if application_method else ''

            # HTML 템플릿에 데이터 삽입 (템플릿 파일이 있는 경우만)
            html_contents = None
            if html_template:
                html_contents = html_template.format(
                    title=title,
                    category=category,
                    target=target,
                    schedule_section=schedule_section,
                    application_method_section=application_method_section,
                    important_notes=important_notes.replace('\n', '<br>')
                )

            # 텍스트 버전도 유지 (HTML을 지원하지 않는 클라이언트용)
            # 주요일정을 텍스트로 변환
            schedule_text = ''
            if schedule:
                if isinstance(schedule, str):
                    try:
                        import json
                        schedule_data = json.loads(schedule)
                    except json.JSONDecodeError:
                        schedule_data = [{'description': schedule, 'date': '', 'location': ''}]
                elif isinstance(schedule, list):
                    schedule_data = schedule
                else:
                    schedule_data = [{'description': str(schedule), 'date': '', 'location': ''}]
                
                schedule_items = []
                for item in schedule_data:
                    description = item.get('description', '')
                    date = item.get('date', '')
                    location = item.get('location', '')
                    
                    item_text = f"      - {description}"
                    if date:
                        item_text += f" ({date})"
                    if location:
                        item_text += f" [장소: {location}]"
                    schedule_items.append(item_text)
                
                schedule_text = f"\n    주요일정:\n" + "\n".join(schedule_items)

            text_contents = f"""[SSU-pport 알리미] {category}의 신규 업데이트 내용입니다.

    제목: {title}
    대상: {target}{schedule_text}{(f"\n    신청방법: {application_method}") if application_method else ""}
    세부내용: {important_notes}
"""

            self.logger.info(f"{'HTML' if html_contents else '평문'} 메일 전송 준비: {title}")

            # MIME 메시지 설정
            if html_contents:
                # HTML 이메일
                msg = MIMEMultipart('alternative')
                msg['Subject'] = title
                msg['From'] = sender_email
                
                # To 헤더는 문자열이어야 함 (여러 수신자는 쉼표로 구분)
                if isinstance(receiver_emails, list):
                    msg['To'] = ', '.join(receiver_emails)
                    recipients = receiver_emails
                else:
                    msg['To'] = receiver_emails
                    recipients = [receiver_emails]
                
                # 텍스트와 HTML 버전 모두 첨부
                text_part = MIMEText(text_contents, 'plain', 'utf-8')
                html_part = MIMEText(html_contents, 'html', 'utf-8')
                
                msg.attach(text_part)
                msg.attach(html_part)
            else:
                # 평문 이메일
                msg = MIMEText(text_contents, 'plain', 'utf-8')
                msg['Subject'] = title
                msg['From'] = sender_email
                
                # To 헤더는 문자열이어야 함 (여러 수신자는 쉼표로 구분)
                if isinstance(receiver_emails, list):
                    msg['To'] = ', '.join(receiver_emails)
                    recipients = receiver_emails
                else:
                    msg['To'] = receiver_emails
                    recipients = [receiver_emails]

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, password)
                # sendmail()에는 리스트를 전달
                server.sendmail(sender_email, recipients, msg.as_string())
            self.logger.info(f"{'HTML' if html_contents else '평문'} 메일 전송 성공: {receiver_emails}")

        except Exception as e:
            self.logger.error(f"이메일 전송 중 오류: {e}")
    
    def send(self, data: dict) -> str:
        emails = EmailDB()
        receiver = emails.get_all_subscribers_email_initial()
        
        # notification_id에 대한 구독자가 없는 경우 처리
        notification_id = data['notification_id']
        if notification_id not in receiver:
            self.logger.warning(f"notification_id {notification_id}에 대한 구독자가 없습니다.")
            return f"No subscribers for notification_id {notification_id}"
        
        receiver_emails = receiver[notification_id]
        if not receiver_emails:
            self.logger.warning(f"notification_id {notification_id}의 구독자 목록이 비어있습니다.")
            return f"Empty subscriber list for notification_id {notification_id}"

        self._send_email(receiver_emails, data)
        return f"Email sent to {len(receiver_emails)} subscribers for notification_id {notification_id}"