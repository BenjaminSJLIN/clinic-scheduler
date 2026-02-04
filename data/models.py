from dataclasses import dataclass
from typing import List, Dict
from datetime import date


@dataclass
class Employee:
    """員工資料"""
    name: str
    is_leader: bool
    can_inject: bool
    available_shifts: Dict[int, List[str]]  # {1: ["早", "中"], 2: ["早", "晚"], ...} 1=週一
    is_fulltime: bool
    
    def can_work_on(self, day_of_week: int, shift_time: str) -> bool:
        """
        檢查員工是否能在特定星期幾的特定班次上班
        
        Args:
            day_of_week: 1=週一, 2=週二, ..., 7=週日
            shift_time: "早", "中", "晚"
        
        Returns:
            True 如果可以上班
        """
        if day_of_week not in self.available_shifts:
            return False
        return shift_time in self.available_shifts[day_of_week]


@dataclass
class ShiftRequirement:
    """班次需求"""
    day_of_week: int  # 1=週一, 2=週二, ..., 7=週日
    shift_time: str  # "早", "中", "晚"
    num_people: int
    num_leaders: int
    num_injectors: int
    num_leader_or_injector: int


@dataclass
class TimeOffRequest:
    """請假申請"""
    employee_name: str
    date: date
    shift_time: str  # "早", "中", "晚"


@dataclass
class PreAssignedShift:
    """預先排班"""
    employee_name: str
    date: date
    shift_time: str  # "早", "中", "晚"


@dataclass
class Shift:
    """排班班次"""
    date: date
    shift_time: str  # "早", "中", "晚"
    assigned_employees: List[Employee]
    
    def has_employee(self, employee_name: str) -> bool:
        """檢查是否包含特定員工"""
        return any(emp.name == employee_name for emp in self.assigned_employees)
    
    def count_leaders(self) -> int:
        """計算 leader 數量"""
        return sum(1 for emp in self.assigned_employees if emp.is_leader)
    
    def count_injectors(self) -> int:
        """計算會打針的員工數量"""
        return sum(1 for emp in self.assigned_employees if emp.can_inject)
    
    def count_leader_or_injector(self) -> int:
        """計算 leader 或會打針的員工數量"""
        return sum(1 for emp in self.assigned_employees if emp.is_leader or emp.can_inject)


@dataclass
class Schedule:
    """完整排班表（一個月）"""
    shifts: List[Shift]
    
    def get_shift(self, target_date: date, shift_time: str) -> Shift:
        """取得特定日期和班次"""
        for shift in self.shifts:
            if shift.date == target_date and shift.shift_time == shift_time:
                return shift
        return None
    
    def get_employee_shifts(self, employee_name: str) -> List[Shift]:
        """取得特定員工的所有班次"""
        return [shift for shift in self.shifts if shift.has_employee(employee_name)]
