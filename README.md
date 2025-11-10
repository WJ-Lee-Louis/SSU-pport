# SSU-pport
Student Notification Service Powered by LLM and Langgraph

<img width="548" height="281" alt="image" src="https://github.com/user-attachments/assets/a31c367d-76c0-4292-83af-f6229a3cc70e" />

## 1. Project Background and Objectives
- The recent **interface update of the SSU-PATH Student Activity Management System** has weakened the readability and clarity of information delivery.  
- There is **no integrated platform** to collectively manage and access information scattered across multiple sources such as **extracurricular programs, uSAINT, and academic notices**, and the existing systems lack **personalization based on department affiliation or area of interest**.  
- With the advancement of **AI Agent technologies**—enabling web data fetching, real-time information extraction, and email/calendar integration—there is now an opportunity to build a **real-time, personalized notification service**.

---

## 2. User Definition
- Students who want to receive **integrated and efficient notifications** from their **major or double-major department**.  
- Students who wish to be **notified of extracurricular programs** related to their **specific interests**.  
- Students who want **automatic notifications** and **calendar synchronization** for key academic events.

---

## 3. Service Pipeline

### ① User and Subscription Management
- Through a **web interface**, users input the **websites they wish to subscribe to** and the **email address** for receiving notifications.  
- The system **stores and manages user preferences** in a database, which are then used for automated alert delivery.

### ② Scheduled Website Monitoring System
- The system **automatically checks subscribed websites** at regular intervals.  
- Through **web crawling**, it compares new data against existing records to **detect updates**.  
- Updated URLs are either **passed to the LLM Agent** for processing or excluded if no changes are found.

### ③ AI Agent for Page Processing and Notification Delivery
- The **AI Agent** reviews the **content of newly updated URLs**.  
- If images or posters are detected, **OCR and content-fetching** processes are performed alongside text extraction.  
- The Agent then **sends summarized content** to the user via email and, if requested, **synchronizes important dates to the user’s calendar**.

---

## 4. Expected Outcomes
- Enhances **efficiency and accessibility** by providing personalized academic and program information.  
- Promotes **student engagement** and strengthens the **synergy between students and academic administration**.  
- The **automated website monitoring framework** could be scaled and adapted for **other universities or institutions**.

---

## 5. Future Plans

### ① Expansion and Automation of the Website Monitoring System
- Build an **LLM-driven flexible crawler** capable of dynamically adapting to various website structures.  
- Enable scalability for deployment at **other universities or institutions**.

### ② Diversification of Notification Platforms
- Extend notification delivery beyond email to **Discord, KakaoTalk**, and other platforms.  
- Allow users to **customize their preferred notification channels**.

### ③ Secure Access to Login-Restricted Websites
- Extend the system to manage **user authentication data** for login-required sites.  
- Implement **automated authentication, session management, and enhanced security** mechanisms.
