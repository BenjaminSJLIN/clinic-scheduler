"""
診所排班應用程式
Clinic Scheduling Application

使用 Streamlit 建立的排班系統
"""
import streamlit as st
import os
from datetime import datetime, timedelta

from data.sheets_manager import SheetsManager
from ui.calendar_view import render_calendar_view
from ui.admin_panel import render_login_panel, render_logout_button, render_config_editor, render_employee_editor
from ui.schedule_generator import (
    render_time_off_input,
    render_pre_assigned_input,
    render_schedule_generator
)


# 頁面設定
st.set_page_config(
    page_title="診所排班系統",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_connection():
    """初始化 Google Sheets 連線"""
    if 'sheets_manager' not in st.session_state:
        # 優先從 Streamlit Secrets 讀取憑證 (線上部署)
        credentials_dict = None
        credentials_path = None
        
        try:
            # 嘗試從 Streamlit Secrets 讀取
            if "google_credentials" in st.secrets:
                credentials_dict = dict(st.secrets["google_credentials"])
        except:
            pass
        
        # 如果沒有 Secrets,檢查本地憑證檔案 (本地開發)
        if credentials_dict is None:
            credentials_path = "credentials.json"
            if not os.path.exists(credentials_path):
                st.error("❌ 找不到憑證")
                st.info("""
                **本地開發**: 請將 `credentials.json` 放在專案根目錄
                
                **線上部署**: 請在 Streamlit Cloud 設定中添加 Secrets
                
                詳細說明請參考 DEPLOYMENT.md
                """)
                st.stop()
        
        # 讀取試算表 ID (優先從 Secrets,其次從 config.py,最後從 session state)
        spreadsheet_id = None
        
        # 1. 嘗試從 Streamlit Secrets 讀取
        try:
            if "spreadsheet_id" in st.secrets:
                spreadsheet_id = st.secrets["spreadsheet_id"]
                st.session_state.spreadsheet_id = spreadsheet_id
        except:
            pass
        
        # 2. 嘗試從 config.py 讀取
        if spreadsheet_id is None:
            try:
                import config
                if hasattr(config, 'SPREADSHEET_ID') and config.SPREADSHEET_ID:
                    spreadsheet_id = config.SPREADSHEET_ID
                    st.session_state.spreadsheet_id = spreadsheet_id
            except ImportError:
                pass
        
        # 3. 從 session state 讀取
        if spreadsheet_id is None and 'spreadsheet_id' in st.session_state:
            spreadsheet_id = st.session_state.spreadsheet_id
        
        # 4. 如果還是沒有，要求使用者輸入
        if spreadsheet_id is None:
            st.markdown("## 🏥 診所排班系統")
            st.markdown("### 首次設定")
            
            st.info("💡 提示：您可以將試算表 ID 寫在 config.py 中，或在 Streamlit Secrets 中設定")
            
            spreadsheet_id = st.text_input(
                "請輸入 Google 試算表 ID",
                help="開啟試算表，從 URL 中複製 ID：https://docs.google.com/spreadsheets/d/[ID]/edit"
            )
            
            if st.button("連線", type="primary"):
                if spreadsheet_id:
                    st.session_state.spreadsheet_id = spreadsheet_id
                    st.rerun()
                else:
                    st.warning("請輸入試算表 ID")
            
            st.stop()
        
        # 建立連線
        sheets_manager = SheetsManager(
            credentials_path=credentials_path,
            credentials_dict=credentials_dict,
            spreadsheet_id=spreadsheet_id
        )
        
        if not sheets_manager.connect():
            st.error("❌ 連線失敗，請檢查憑證和試算表 ID")
            if st.button("重新設定"):
                st.session_state.spreadsheet_id = None
                st.rerun()
            st.stop()
        
        st.session_state.sheets_manager = sheets_manager


def load_data():
    """載入資料"""
    sheets_manager = st.session_state.sheets_manager
    
    # 載入員工名單
    if 'employees' not in st.session_state:
        st.session_state.employees = sheets_manager.get_employees()
    
    # 載入班次設定
    if 'requirements' not in st.session_state:
        st.session_state.requirements = sheets_manager.get_config()
    
    # 載入管理員帳密
    if 'admin_credentials' not in st.session_state:
        st.session_state.admin_credentials = sheets_manager.get_admin_credentials()


def main():
    """主程式"""
    # 初始化連線
    init_connection()
    
    # 載入資料
    load_data()
    
    sheets_manager = st.session_state.sheets_manager
    employees = st.session_state.employees
    requirements = st.session_state.requirements
    admin_credentials = st.session_state.admin_credentials
    
    # 標題
    st.title("🏥 診所排班系統")
    
    # 側邊欄
    with st.sidebar:
        st.markdown("## 選單")
        
        # 管理員登入
        is_admin = render_login_panel(admin_credentials)
        
        if is_admin:
            st.success("✅ 已登入為管理員")
            render_logout_button()
            
            # 管理員選單
            st.markdown("---")
            menu = st.radio(
                "功能選單",
                ["📅 查看排班", "🎯 生成排班", "⚙️ 班次設定", "👥 員工管理"]
            )
        else:
            # 一般使用者選單
            st.info("👁️ 查看模式（唯讀）")
            menu = st.radio(
                "功能選單",
                ["📅 查看排班"]
            )
    
    # 主要內容
    if menu == "📅 查看排班":
        st.markdown("## 📅 查看排班表")
        
        # 取得已儲存的排班列表
        saved_schedules = sheets_manager.get_saved_schedule_list()
        
        if not saved_schedules:
            st.info("尚未儲存任何排班表，請前往「生成排班」功能生成並儲存排班")
        else:
            # 建立選項列表（只包含已儲存的排班）
            schedule_options = []
            for sch in saved_schedules:
                schedule_options.append(f"{sch['name']} (儲存於 {sch['saved_at']})")
            
            # 下拉選單
            selected_option = st.selectbox(
                "選擇要查看的排班表",
                schedule_options,
                help="選擇要查看的已儲存排班表"
            )
            
            # 載入選擇的排班
            schedule_to_display = None
            start_date_to_display = None
            
            for sch in saved_schedules:
                option_text = f"{sch['name']} (儲存於 {sch['saved_at']})"
                if option_text == selected_option:
                    with st.spinner("載入排班表..."):
                        schedule_to_display = sheets_manager.load_schedule(
                            sch['name'],
                            sch['saved_at']
                        )
                        # 解析開始日期
                        try:
                            start_date_to_display = datetime.strptime(sch['start_date'], '%Y-%m-%d').date()
                        except:
                            start_date_to_display = datetime.now().date()
                    break
            
            # 顯示排班表
            if schedule_to_display:
                render_calendar_view(schedule_to_display, start_date_to_display)
                
                # 管理員刪除功能
                if is_admin:
                    st.markdown("---")
                    st.markdown("### 🗑️ 管理功能（僅管理員）")
                    
                    # 找出當前選擇的排班資訊
                    current_schedule_info = None
                    for sch in saved_schedules:
                        option_text = f"{sch['name']} (儲存於 {sch['saved_at']})"
                        if option_text == selected_option:
                            current_schedule_info = sch
                            break
                    
                    if current_schedule_info:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.warning(f"⚠️ 您即將刪除排班：**{current_schedule_info['name']}** (儲存於 {current_schedule_info['saved_at']})")
                        with col2:
                            if st.button("🗑️ 刪除此排班", type="secondary", use_container_width=True):
                                # 確認刪除
                                success = sheets_manager.delete_schedule(
                                    current_schedule_info['name'],
                                    current_schedule_info['saved_at']
                                )
                                
                                if success:
                                    st.success("✅ 排班已刪除")
                                    st.info("請重新整理頁面以更新排班列表")
                                    st.rerun()
                                else:
                                    st.error("❌ 刪除失敗，請檢查 Google Sheets 連線")
            else:
                st.error("載入排班表失敗，請重試")
    
    elif menu == "🎯 生成排班" and is_admin:
        st.markdown("## 🎯 生成排班表")
        
        # 檢查是否有員工
        if not employees:
            st.error("❌ 尚未設定員工名單，請管理員先新增員工")
            st.stop()
        
        # 請假與預排班輸入
        col1, col2 = st.columns(2)
        
        with col1:
            render_time_off_input(employees, sheets_manager)
        
        with col2:
            render_pre_assigned_input(employees, sheets_manager)
        
        st.markdown("---")
        
        # 載入最新的請假和預排班資料
        time_off_requests = sheets_manager.get_time_off_requests()
        pre_assigned_shifts = sheets_manager.get_pre_assigned_shifts()
        
        # 排班生成器
        render_schedule_generator(
            employees=employees,
            requirements=requirements,
            time_off_requests=time_off_requests,
            pre_assigned_shifts=pre_assigned_shifts,
            sheets_manager=sheets_manager
        )
    
    elif menu == "⚙️ 班次設定" and is_admin:
        st.markdown("## ⚙️ 班次需求設定")
        render_config_editor(requirements, sheets_manager)
    
    elif menu == "👥 員工管理" and is_admin:
        st.markdown("## 👥 員工名單管理")
        render_employee_editor(employees, sheets_manager)
    
    # 頁腳
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <small>診所排班系統 v1.0 | 使用 Streamlit 建立</small>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
