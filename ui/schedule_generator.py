"""
排班生成器 UI 元件
"""
import streamlit as st
from datetime import datetime, date, timedelta
from typing import List
from data.models import TimeOffRequest, PreAssignedShift, Employee, Schedule
from scheduler.ortools_scheduler import ORToolsScheduler


def render_time_off_input(employees: List[Employee], sheets_manager):
    """
    渲染請假輸入介面
    
    Args:
        employees: 員工列表
        sheets_manager: Google Sheets 管理器
    """
    st.markdown("### 📋 請假申請")
    
    # 顯示現有請假
    time_off_requests = sheets_manager.get_time_off_requests()
    
    if time_off_requests:
        st.markdown("#### 📝 現有請假")
        
        # 使用container的height参数来创建固定高度的滚动区域
        with st.container(height=300):
            for req in time_off_requests:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.info(f"👤 {req.employee_name} - {req.date.strftime('%Y-%m-%d')} {req.shift_time}班")
                with col2:
                    if st.button("🗑️", key=f"del_timeoff_{req.employee_name}_{req.date}_{req.shift_time}"):
                        sheets_manager.remove_time_off_request(
                            req.employee_name,
                            req.date.strftime('%Y-%m-%d'),
                            req.shift_time
                        )
                        st.rerun()
    
    # 新增請假 - 在expander外面
    st.markdown("#### 🆕 新增請假")
    with st.form("time_off_form"):
        cols = st.columns([2, 2, 1])
        
        with cols[0]:
            employee_name = st.selectbox(
                "員工",
                [emp.name for emp in employees]
            )
        with cols[1]:
            request_date = st.date_input("日期", value=datetime.now().date())
        with cols[2]:
            shift_time = st.selectbox("班次", ["早", "中", "晚", "全天"])
        
        submit = st.form_submit_button("➕ 新增請假", type="primary")
        
        if submit:
            # 如果選擇全天，則新增早、中、晚三個請假記錄
            if shift_time == "全天":
                success_count = 0
                for time in ["早", "中", "晚"]:
                    new_request = TimeOffRequest(
                        employee_name=employee_name,
                        date=request_date,
                        shift_time=time
                    )
                    if sheets_manager.add_time_off_request(new_request):
                        success_count += 1
                
                if success_count == 3:
                    st.success(f"✅ 已新增全天請假：{employee_name} {request_date} (早、中、晚)")
                    st.rerun()
                elif success_count > 0:
                    st.warning(f"⚠️ 部分新增成功：已新增 {success_count}/3 個班次")
                    st.rerun()
                else:
                    st.error("❌ 新增失敗")
            else:
                # 單一班次請假
                new_request = TimeOffRequest(
                    employee_name=employee_name,
                    date=request_date,
                    shift_time=shift_time
                )
                if sheets_manager.add_time_off_request(new_request):
                    st.success(f"✅ 已新增請假：{employee_name} {request_date} {shift_time}班")
                    st.rerun()
                else:
                    st.error("❌ 新增失敗")


def render_pre_assigned_input(employees: List[Employee], sheets_manager):
    """
    渲染預先排班輸入介面
    
    Args:
        employees: 員工列表
        sheets_manager: Google Sheets 管理器
    """
    st.markdown("### 📌 預先排班")
    
    # 顯示現有預排班
    pre_assigned = sheets_manager.get_pre_assigned_shifts()
    
    if pre_assigned:
        st.markdown("#### 📋 現有預排班")
        
        # 使用container的height参数来创建固定高度的滚动区域
        with st.container(height=300):
            for shift in pre_assigned:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.success(f"✅ {shift.employee_name} - {shift.date.strftime('%Y-%m-%d')} {shift.shift_time}班")
                with col2:
                    if st.button("🗑️", key=f"del_{shift.employee_name}_{shift.date}_{shift.shift_time}"):
                        sheets_manager.remove_pre_assigned_shift(
                            shift.employee_name,
                            shift.date.strftime('%Y-%m-%d'),
                            shift.shift_time
                        )
                        st.rerun()
    
    # 新增預排班 - 在expander外面
    st.markdown("#### 🆕 新增預排班")
    with st.form("pre_assigned_form"):
        cols = st.columns([2, 2, 1])
        
        with cols[0]:
            employee_name = st.selectbox(
                "員工",
                [emp.name for emp in employees],
                key="pre_emp"
            )
        with cols[1]:
            shift_date = st.date_input("日期", value=datetime.now().date(), key="pre_date")
        with cols[2]:
            shift_time = st.selectbox("班次", ["早", "中", "晚"], key="pre_shift")
        
        submit = st.form_submit_button("➕ 新增預排班", type="primary")
        
        if submit:
            new_pre = PreAssignedShift(
                employee_name=employee_name,
                date=shift_date,
                shift_time=shift_time
            )
            if sheets_manager.add_pre_assigned_shift(new_pre):
                st.success(f"✅ 已新增預排班：{employee_name} {shift_date} {shift_time}班")
                st.rerun()
            else:
                st.error("❌ 新增失敗")


def render_schedule_generator(
    employees: List[Employee],
    requirements,
    time_off_requests,
    pre_assigned_shifts,
    sheets_manager
):
    """
    渲染排班生成器
    
    Args:
        employees: 員工列表
        requirements: 班次需求
        time_off_requests: 請假申請
        pre_assigned_shifts: 預排班
        sheets_manager: Google Sheets 管理器
    
    Returns:
        生成的排班列表（如果有）
    """
    st.markdown("### 🎯 生成排班表")
    
    # 設定參數
    with st.form("generator_form"):
        start_date = st.date_input(
            "開始日期（週一）",
            value=datetime.now().date()
        )
        
        # 固定為一週
        num_weeks = 1
        
        # 確保是週一
        if start_date.weekday() != 0:
            st.warning("⚠️ 開始日期必須是週一")
            start_date = start_date - timedelta(days=start_date.weekday())
            st.info(f"已調整為最近的週一：{start_date}")
        
        generate = st.form_submit_button("🚀 生成排班表", type="primary")
    
    if generate:
        with st.spinner("正在搜尋排班方案..."):
            # 使用 OR-Tools 排班器
            scheduler = ORToolsScheduler(
                employees=employees,
                requirements=requirements,
                time_off_requests=time_off_requests,
                pre_assigned_shifts=pre_assigned_shifts,
                start_date=start_date,
                num_weeks=num_weeks,
                max_time_seconds=300  # 5 分鐘
            )
            
            # 生成排班
            schedules, diagnostics = scheduler.generate_schedules()
            
            # 儲存到 session state
            st.session_state.generated_schedules = schedules
            st.session_state.start_date = start_date
            st.session_state.diagnostics = diagnostics
            
            # 顯示結果
            if schedules:
                # 檢查是否使用了放寬條件
                relaxed_info = st.session_state.get('relaxed_info', {})
                if any(relaxed_info.values()):
                    st.success(f"✅ 找到 {len(schedules)} 個有效排班方案！（使用放寬條件）")
                else:
                    st.success(f"✅ 找到 {len(schedules)} 個有效排班方案！")
                
                # 顯示診斷資訊
                diag_msg = f"""
                **演算法**: OR-Tools CP-SAT  
                **狀態**: {diagnostics.get('solver_status', 'N/A')}  
                **求解時間**: {diagnostics.get('solve_time', 0):.2f}秒  
                **內部分支數**: {diagnostics.get('num_branches', 0):,}
                """
                
                # 顯示放寬條件資訊
                if relaxed_info.get('requirements'):
                    diag_msg += "\n**放寬**: 班次需求減半"
                if relaxed_info.get('shifts'):
                    diag_msg += "\n**放寬**: 允許每週 8-11 班"
                if relaxed_info.get('days_off'):
                    diag_msg += "\n**放寬**: 允許每週只休 1 天"
                
                st.info(diag_msg)
            else:
                st.error("❌ 找不到符合條件的排班方案")
                st.warning("請在下方嘗試放寬條件")
                
                # 顯示診斷資訊
                if diagnostics:
                    st.info(f"""
                    **求解狀態**: {diagnostics.get('solver_status', 'N/A')}  
                    **求解時間**: {diagnostics.get('solve_time', 0):.2f}秒  
                    **衝突數**: {diagnostics.get('num_conflicts', 0):,}  
                    **分支數**: {diagnostics.get('num_branches', 0):,}
                    """)
    
    # 顯示生成的排班選項
    if 'generated_schedules' in st.session_state and st.session_state.generated_schedules:
        render_schedule_selector(
            st.session_state.generated_schedules,
            st.session_state.start_date,
            sheets_manager
        )
    
    # 如果有失敗的診斷資訊，顯示放寬條件選項
    if 'diagnostics' in st.session_state and not st.session_state.get('generated_schedules'):
        st.markdown("---")
        render_constraint_relaxation(
            employees,
            requirements,
            time_off_requests,
            pre_assigned_shifts,
            st.session_state.get('start_date', datetime.now().date()),
            num_weeks
        )


def render_constraint_relaxation(
    employees,
    requirements,
    time_off_requests,
    pre_assigned_shifts,
    start_date,
    num_weeks
):
    """
    渲染條件放寬選項
    
    Args:
        employees: 員工列表
        requirements: 班次需求
        time_off_requests: 請假申請
        pre_assigned_shifts: 預排班
        start_date: 開始日期
        num_weeks: 週數
    """
    st.markdown("### 🔧 放寬條件")
    
    st.info("""
    無法找到符合所有條件的排班方案。您可以選擇放寬以下條件：
    """)
    
    with st.form("relax_form"):
        relax_requirements = st.checkbox(
            "放寬班次需求（Leader/打針人數減半）",
            value=True
        )
        relax_shifts = st.checkbox(
            "放寬正職班次數（允許每週 8-11 班）",
            value=False
        )
        relax_days_off = st.checkbox(
            "放寬休假天數（允許每週只休 1 天）",
            value=False
        )
        
        regenerate = st.form_submit_button("🔄 重新生成", type="secondary")
    
    if regenerate:
        with st.spinner("正在以放寬條件搜尋..."):
            # 建立 OR-Tools 排班器並設定放寬條件
            scheduler = ORToolsScheduler(
                employees=employees,
                requirements=requirements,
                time_off_requests=time_off_requests,
                pre_assigned_shifts=pre_assigned_shifts,
                start_date=start_date,
                num_weeks=num_weeks,
                max_time_seconds=300
            )
            
            scheduler.relax_constraints(
                requirements=relax_requirements,
                shifts=relax_shifts,
                days_off=relax_days_off
            )
            
            # 生成排班
            schedules, diagnostics = scheduler.generate_schedules()
            
            # 儲存到 session state（包括放寬條件資訊）
            st.session_state.generated_schedules = schedules
            st.session_state.start_date = start_date
            st.session_state.diagnostics = diagnostics
            st.session_state.relaxed_info = {
                'requirements': relax_requirements,
                'shifts': relax_shifts,
                'days_off': relax_days_off
            }
            
            # 強制重新整理，讓主函數顯示結果
            st.rerun()


def render_schedule_selector(schedules: List[Schedule], start_date: date, sheets_manager):
    """
    渲染排班方案顯示（現在只有一個方案）
    
    Args:
        schedules: 排班方案列表
        start_date: 開始日期
        sheets_manager: Google Sheets 管理器
    """
    if not schedules:
        return
    
    st.markdown("### 📊 排班結果")
    
    # 直接顯示第一個（也是唯一的）排班方案
    selected_schedule = schedules[0]
    
    # 匯入日曆視圖
    from ui.calendar_view import render_calendar_view
    render_calendar_view(selected_schedule, start_date)
    
    # 按鈕區
    st.markdown("---")
    
    # 儲存按鈕
    if st.button("💾 儲存排班表", type="primary", use_container_width=True):
        schedule_name = start_date.strftime('%Y-%m-%d')
        success = sheets_manager.save_schedule(selected_schedule, start_date)
        
        if success:
            st.success(f"✅ 已儲存排班表：{schedule_name}")
            st.info("💡 您可以在「查看排班」頁面載入已儲存的排班表")
        else:
            st.error("❌ 儲存失敗，請檢查 Google Sheets 連線")


