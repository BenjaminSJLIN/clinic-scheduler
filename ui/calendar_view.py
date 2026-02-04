"""
日曆視圖 UI 元件
"""
import streamlit as st
from datetime import timedelta
from data.models import Schedule


def render_calendar_view(schedule: Schedule, start_date):
    """
    渲染月曆視圖
    
    Args:
        schedule: 排班表
        start_date: 開始日期（週一）
    """
    st.markdown("### 📅 月度排班表")
    
    # 計算週數
    all_dates = set(shift.date for shift in schedule.shifts)
    if not all_dates:
        st.warning("沒有排班資料")
        return
    
    min_date = min(all_dates)
    max_date = max(all_dates)
    num_weeks = ((max_date - min_date).days // 7) + 1
    
    # 班次顏色
    shift_colors = {
        "早": "#FFE5E5",  # 淺紅
        "中": "#E5F5FF",  # 淺藍
        "晚": "#FFF5E5"   # 淺黃
    }
    
    # 按週渲染
    for week in range(num_weeks):
        week_start = start_date + timedelta(weeks=week)
        
        st.markdown(f"#### 第 {week + 1} 週")
        
        # 建立表格標題
        cols = st.columns(7)
        days = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
        
        for i, day in enumerate(days):
            with cols[i]:
                current_date = week_start + timedelta(days=i)
                st.markdown(f"**{day}**  \n{current_date.strftime('%m/%d')}")
        
        # 渲染每個班次
        for shift_time in ["早", "中", "晚"]:
            cols = st.columns(7)
            
            for day_idx in range(7):
                current_date = week_start + timedelta(days=day_idx)
                
                # 找出此日期和班次的排班
                matching_shift = None
                for shift in schedule.shifts:
                    if shift.date == current_date and shift.shift_time == shift_time:
                        matching_shift = shift
                        break
                
                with cols[day_idx]:
                    if matching_shift and matching_shift.assigned_employees:
                        # 檢查特殊需求（週一和週五早上需要 4 人）
                        day_of_week = current_date.weekday() + 1
                        is_special = (day_of_week in [1, 5] and shift_time == "早")
                        
                        # 渲染員工卡片
                        bg_color = shift_colors.get(shift_time, "#F0F0F0")
                        border = "2px solid #FF6B6B" if is_special else "1px solid #DDD"
                        
                        employees_html = "<br>".join([
                            f"{'🔹' if emp.is_leader else '⚡' if emp.can_inject else '👤'} {emp.name}"
                            for emp in matching_shift.assigned_employees
                        ])
                        
                        st.markdown(
                            f"""
                            <div style="
                                background-color: {bg_color};
                                border: {border};
                                border-radius: 5px;
                                padding: 8px;
                                margin: 2px 0;
                                font-size: 12px;
                            ">
                                <strong>{shift_time}</strong><br>
                                {employees_html}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    else:
                        # 空班次
                        st.markdown(
                            f"""
                            <div style="
                                background-color: #F9F9F9;
                                border: 1px dashed #CCC;
                                border-radius: 5px;
                                padding: 8px;
                                margin: 2px 0;
                                text-align: center;
                                color: #999;
                                font-size: 12px;
                            ">
                                {shift_time}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
        
        # 計算並顯示當週每人的排班數
        st.markdown("##### 🔢 當週排班統計")
        
        shift_counts = {}
        week_end = week_start + timedelta(days=6)
        
        # 篩選當週的排班
        current_week_shifts = [
            s for s in schedule.shifts 
            if week_start <= s.date <= week_end
        ]
        
        # 計算每人班次
        for shift in current_week_shifts:
            for emp in shift.assigned_employees:
                shift_counts[emp.name] = shift_counts.get(emp.name, 0) + 1
        
        # 顯示統計結果
        if shift_counts:
            # 依班次數由多到少排序
            sorted_counts = sorted(shift_counts.items(), key=lambda x: x[1], reverse=True)
            
            # 使用多欄顯示
            num_cols = 6
            stat_cols = st.columns(num_cols)
            
            for idx, (name, count) in enumerate(sorted_counts):
                with stat_cols[idx % num_cols]:
                    st.info(f"{name}: {count}")
        else:
            st.caption("尚無排班資料")

        st.markdown("---")
    
    # 圖例
    st.markdown("#### 圖例")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("🔹 Leader")
    with col2:
        st.markdown("⚡ 會打針")
    with col3:
        st.markdown("👤 一般員工")
