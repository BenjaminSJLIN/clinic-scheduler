"""
排班約束條件驗證
"""
from typing import List, Dict, Set
from datetime import date, timedelta
from collections import defaultdict
from data.models import Employee, Shift, ShiftRequirement, TimeOffRequest, PreAssignedShift, Schedule


def validate_shift_requirements(
    shift: Shift,
    requirement: ShiftRequirement,
    relaxed: bool = False
) -> bool:
    """
    驗證班次是否符合人員需求
    
    Args:
        shift: 班次資料
        requirement: 需求設定
        relaxed: 是否放寬條件
    """
    # 檢查人數
    if len(shift.assigned_employees) != requirement.num_people:
        return False
    
    # 檢查 leader 數量
    leader_count = shift.count_leaders()
    if relaxed:
        # 放寬：至少有一半的 leader 需求
        if leader_count < requirement.num_leaders // 2:
            return False
    else:
        if leader_count < requirement.num_leaders:
            return False
    
    # 檢查打針人員數量
    injector_count = shift.count_injectors()
    if relaxed:
        # 放寬：至少有一半的打針需求
        if injector_count < requirement.num_injectors // 2:
            return False
    else:
        if injector_count < requirement.num_injectors:
            return False
    
    # 檢查 leader 或打針人員數量
    leader_or_injector_count = shift.count_leader_or_injector()
    if relaxed:
        # 放寬：至少有一半的需求
        if leader_or_injector_count < requirement.num_leader_or_injector // 2:
            return False
    else:
        if leader_or_injector_count < requirement.num_leader_or_injector:
            return False
    
    return True


def validate_fulltime_constraints(
    schedule: Schedule,
    employee: Employee,
    relaxed_shifts: bool = False,
    relaxed_days_off: bool = False
) -> bool:
    """
    驗證正職員工約束條件
    
    Args:
        schedule: 完整排班表
        employee: 員工資料
        relaxed_shifts: 放寬班次數量限制（允許 8-9 班）
        relaxed_days_off: 放寬休假天數限制（允許只休 1 天）
    """
    if not employee.is_fulltime:
        return True
    
    # 取得該員工的所有班次
    employee_shifts = schedule.get_employee_shifts(employee.name)
    
    # 按週分組
    weekly_shifts = defaultdict(list)
    for shift in employee_shifts:
        # 計算週數（以週一為一週的開始）
        week_start = shift.date - timedelta(days=shift.date.weekday())
        weekly_shifts[week_start].append(shift)
    
    # 檢查每週
    for week_start, shifts in weekly_shifts.items():
        # 檢查班次數量（每週 10 班）
        if relaxed_shifts:
            # 放寬：允許 8-10 班
            if len(shifts) < 8 or len(shifts) > 10:
                return False
        else:
            if len(shifts) != 10:
                return False
        
        # 檢查休假天數（每週休 2 天）
        work_days = set()
        for shift in shifts:
            work_days.add(shift.date)
        
        # 計算該週的所有日期
        week_dates = set()
        for i in range(7):
            week_dates.add(week_start + timedelta(days=i))
        
        # 休假天數
        days_off = len(week_dates - work_days)
        
        if relaxed_days_off:
            # 放寬：至少休 1 天
            if days_off < 1:
                return False
        else:
            # 嚴格：必須休 2 天
            if days_off != 2:
                return False
    
    return True


def validate_availability(
    shift: Shift,
    employee: Employee,
    time_off_requests: List[TimeOffRequest]
) -> bool:
    """
    驗證員工是否可以上該班次
    
    Args:
        shift: 班次資料
        employee: 員工資料
        time_off_requests: 請假申請列表
    """
    # 檢查員工是否可上該星期幾的該時段
    day_of_week = shift.date.weekday() + 1  # 1=週一, 7=週日
    if not employee.can_work_on(day_of_week, shift.shift_time):
        return False
    
    # 檢查是否有請假
    for request in time_off_requests:
        if (request.employee_name == employee.name and
            request.date == shift.date and
            request.shift_time == shift.shift_time):
            return False
    
    return True


def validate_pre_assignments(
    shift: Shift,
    pre_assigned_shifts: List[PreAssignedShift]
) -> bool:
    """
    驗證預先排班是否包含在班次中
    
    Args:
        shift: 班次資料
        pre_assigned_shifts: 預先排班列表
    """
    # 找出此班次的所有預先排班
    required_employees = []
    for pre in pre_assigned_shifts:
        if pre.date == shift.date and pre.shift_time == shift.shift_time:
            required_employees.append(pre.employee_name)
    
    # 檢查是否都包含在班次中
    assigned_names = [emp.name for emp in shift.assigned_employees]
    for required in required_employees:
        if required not in assigned_names:
            return False
    
    return True


def calculate_schedule_score(schedule: Schedule) -> float:
    """
    計算排班表的偏好分數
    
    偏好：上班的人一天盡量排兩班
    
    Args:
        schedule: 完整排班表
        
    Returns:
        分數（越高越好）
    """
    score = 0.0
    
    # 統計每個員工每天的班次數
    daily_shifts = defaultdict(lambda: defaultdict(int))
    
    for shift in schedule.shifts:
        for employee in shift.assigned_employees:
            daily_shifts[employee.name][shift.date] += 1
    
    # 計算分數
    for employee_name, date_shifts in daily_shifts.items():
        for shift_date, count in date_shifts.items():
            # 一天兩班：+10 分
            if count == 2:
                score += 10
            # 一天一班：+0 分
            elif count == 1:
                score += 0
            # 一天三班：-5 分（避免過勞）
            else:
                score -= 5
    
    return score


def check_employee_day_limit(
    schedule: Schedule,
    employee_name: str,
    target_date: date,
    max_shifts_per_day: int = 3
) -> bool:
    """
    檢查員工在特定日期的班次數是否超過限制
    
    Args:
        schedule: 當前排班表
        employee_name: 員工姓名
        target_date: 目標日期
        max_shifts_per_day: 每天最多班次數
        
    Returns:
        True 如果未超過限制
    """
    count = 0
    for shift in schedule.shifts:
        if shift.date == target_date and shift.has_employee(employee_name):
            count += 1
    
    return count < max_shifts_per_day
