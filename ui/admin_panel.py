"""
管理員面板 UI 元件
"""
import streamlit as st
from typing import Dict
from data.models import Employee, ShiftRequirement


def render_login_panel(admin_credentials: Dict[str, str]) -> bool:
    """
    渲染登入面板
    
    Args:
        admin_credentials: 管理員帳密字典
        
    Returns:
        True 如果已成功登入
    """
    # 檢查 session state
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    
    if st.session_state.is_admin:
        return True
    
    # 登入表單
    st.sidebar.markdown("### 🔐 管理員登入")
    
    with st.sidebar.form("login_form"):
        username = st.text_input("帳號")
        password = st.text_input("密碼", type="password")
        submit = st.form_submit_button("登入")
        
        if submit:
            if username in admin_credentials and admin_credentials[username] == password:
                st.session_state.is_admin = True
                st.rerun()
            else:
                st.error("帳號或密碼錯誤")
    
    return False


def render_logout_button():
    """渲染登出按鈕"""
    if st.sidebar.button("🚪 登出"):
        st.session_state.is_admin = False
        st.rerun()


def render_config_editor(requirements, sheets_manager):
    """
    渲染設定檔編輯器
    
    Args:
        requirements: 當前班次需求列表
        sheets_manager: Google Sheets 管理器
    """
    st.markdown("### ⚙️ 班次需求設定")
    
    st.info("設定每週各班次的人員需求")
    
    # 建立可編輯的資料框
    days = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    shifts = ["早", "中", "晚"]
    
    # 建立需求字典方便查詢
    req_dict = {}
    for req in requirements:
        key = (req.day_of_week, req.shift_time)
        req_dict[key] = req
    
    # 使用表格形式編輯
    for shift_time in shifts:
        st.markdown(f"#### {shift_time}班")
        
        cols = st.columns([1, 1, 1, 1, 1])
        cols[0].markdown("**星期**")
        cols[1].markdown("**人數**")
        cols[2].markdown("**Leader數**")
        cols[3].markdown("**打針數**")
        cols[4].markdown("**Leader或打針**")
        
        for day_idx, day_name in enumerate(days, start=1):
            cols = st.columns([1, 1, 1, 1, 1])
            
            key = (day_idx, shift_time)
            req = req_dict.get(key, ShiftRequirement(
                day_of_week=day_idx,
                shift_time=shift_time,
                num_people=3,
                num_leaders=1,
                num_injectors=1,
                num_leader_or_injector=2
            ))
            
            with cols[0]:
                st.markdown(day_name)
            with cols[1]:
                num_people = st.number_input(
                    "人數",
                    min_value=1,
                    max_value=10,
                    value=req.num_people,
                    key=f"people_{day_idx}_{shift_time}",
                    label_visibility="collapsed"
                )
            with cols[2]:
                num_leaders = st.number_input(
                    "Leader數",
                    min_value=0,
                    max_value=10,
                    value=req.num_leaders,
                    key=f"leaders_{day_idx}_{shift_time}",
                    label_visibility="collapsed"
                )
            with cols[3]:
                num_injectors = st.number_input(
                    "打針數",
                    min_value=0,
                    max_value=10,
                    value=req.num_injectors,
                    key=f"injectors_{day_idx}_{shift_time}",
                    label_visibility="collapsed"
                )
            with cols[4]:
                num_leader_or_injector = st.number_input(
                    "Leader或打針",
                    min_value=0,
                    max_value=10,
                    value=req.num_leader_or_injector,
                    key=f"leader_or_inj_{day_idx}_{shift_time}",
                    label_visibility="collapsed"
                )
            
            # 更新需求
            req_dict[key] = ShiftRequirement(
                day_of_week=day_idx,
                shift_time=shift_time,
                num_people=num_people,
                num_leaders=num_leaders,
                num_injectors=num_injectors,
                num_leader_or_injector=num_leader_or_injector
            )
    
    # 儲存按鈕
    if st.button("💾 儲存設定", type="primary"):
        new_requirements = list(req_dict.values())
        if sheets_manager.update_config(new_requirements):
            st.success("✅ 設定已儲存")
            st.rerun()
        else:
            st.error("❌ 儲存失敗")


def render_employee_editor(employees, sheets_manager):
    """
    渲染員工名單編輯器
    
    Args:
        employees: 當前員工列表
        sheets_manager: Google Sheets 管理器
    """
    st.markdown("### 👥 員工名單管理")
    
    # 顯示現有員工
    st.markdown("#### 現有員工")
    
    if employees:
        for i, emp in enumerate(employees):
            with st.expander(f"{emp.name} - {'正職' if emp.is_fulltime else '兼職'}"):
                cols = st.columns([2, 1, 1, 1])
                
                with cols[0]:
                    name = st.text_input("姓名", value=emp.name, key=f"name_{i}")
                with cols[1]:
                    is_leader = st.checkbox("Leader", value=emp.is_leader, key=f"leader_{i}")
                with cols[2]:
                    can_inject = st.checkbox("打針", value=emp.can_inject, key=f"inject_{i}")
                with cols[3]:
                    is_fulltime = st.checkbox("正職", value=emp.is_fulltime, key=f"full_{i}")
                
                # 可上班時間（按星期幾和班次）
                st.markdown("**可上班時間**")
                
                # 快速設定選項
                quick_set = st.selectbox(
                    "快速設定",
                    ["自訂", "全週全時段", "全週早中班", "全週早晚班", "平日全時段", "週末全時段"],
                    key=f"quick_{i}"
                )
                
                # 根據快速設定初始化
                if quick_set == "全週全時段":
                    default_availability = {d: ["早", "中", "晚"] for d in range(1, 8)}
                elif quick_set == "全週早中班":
                    default_availability = {d: ["早", "中"] for d in range(1, 8)}
                elif quick_set == "全週早晚班":
                    default_availability = {d: ["早", "晚"] for d in range(1, 8)}
                elif quick_set == "平日全時段":
                    default_availability = {d: ["早", "中", "晚"] for d in range(1, 6)}
                elif quick_set == "週末全時段":
                    default_availability = {6: ["早", "中", "晚"], 7: ["早", "中", "晚"]}
                else:
                    default_availability = emp.available_shifts
                
                # 詳細設定
                days = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
                shifts = ["早", "中", "晚"]
                
                # 使用表格形式
                st.markdown("| 星期 | 早 | 中 | 晚 |")
                st.markdown("|------|----|----|-----|")
                
                new_availability = {}
                for day_idx, day_name in enumerate(days, start=1):
                    cols_check = st.columns([1, 1, 1, 1])
                    
                    with cols_check[0]:
                        st.markdown(f"**{day_name}**")
                    
                    day_shifts = []
                    for shift_idx, shift_time in enumerate(shifts):
                        with cols_check[shift_idx + 1]:
                            default_checked = (
                                day_idx in default_availability and 
                                shift_time in default_availability[day_idx]
                            )
                            if st.checkbox(
                                shift_time,
                                value=default_checked,
                                key=f"avail_{i}_{day_idx}_{shift_time}",
                                label_visibility="collapsed"
                            ):
                                day_shifts.append(shift_time)
                    
                    if day_shifts:
                        new_availability[day_idx] = day_shifts
                
                # 更新員工資料
                employees[i] = Employee(
                    name=name,
                    is_leader=is_leader,
                    can_inject=can_inject,
                    available_shifts=new_availability,
                    is_fulltime=is_fulltime
                )
    else:
        st.info("目前沒有員工資料")
    
    # 新增員工
    st.markdown("#### 新增員工")
    with st.form("add_employee_form"):
        cols = st.columns([2, 1, 1, 1])
        
        with cols[0]:
            new_name = st.text_input("姓名")
        with cols[1]:
            new_is_leader = st.checkbox("Leader", key="new_leader")
        with cols[2]:
            new_can_inject = st.checkbox("打針", key="new_inject")
        with cols[3]:
            new_is_fulltime = st.checkbox("正職", value=True, key="new_full")
        
        st.markdown("**可上班時間**")
        
        # 快速設定
        new_quick = st.selectbox(
            "快速設定",
            ["全週全時段", "全週早中班", "全週早晚班", "平日全時段", "週末全時段"],
            key="new_quick"
        )
        
        submit = st.form_submit_button("➕ 新增員工", type="primary")
        
        if submit and new_name:
            # 根據快速設定建立可上班時間
            if new_quick == "全週全時段":
                new_availability = {d: ["早", "中", "晚"] for d in range(1, 8)}
            elif new_quick == "全週早中班":
                new_availability = {d: ["早", "中"] for d in range(1, 8)}
            elif new_quick == "全週早晚班":
                new_availability = {d: ["早", "晚"] for d in range(1, 8)}
            elif new_quick == "平日全時段":
                new_availability = {d: ["早", "中", "晚"] for d in range(1, 6)}
            else:  # 週末全時段
                new_availability = {6: ["早", "中", "晚"], 7: ["早", "中", "晚"]}
            
            new_employee = Employee(
                name=new_name,
                is_leader=new_is_leader,
                can_inject=new_can_inject,
                available_shifts=new_availability,
                is_fulltime=new_is_fulltime
            )
            employees.append(new_employee)
            st.success(f"已新增員工：{new_name}")
    
    # 儲存按鈕
    if st.button("💾 儲存員工名單", type="primary"):
        if sheets_manager.update_employees(employees):
            st.success("✅ 員工名單已儲存")
            st.rerun()
        else:
            st.error("❌ 儲存失敗")
