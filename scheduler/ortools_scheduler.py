"""
OR-Tools CP-SAT Solver 排班演算法
使用 Google OR-Tools 的約束滿足問題求解器來優化排班效能
"""
from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta
from collections import defaultdict
import time

from ortools.sat.python import cp_model

from data.models import (
    Employee, Shift, ShiftRequirement, TimeOffRequest, 
    PreAssignedShift, Schedule
)
from scheduler.constraints import (
    validate_availability,
    calculate_schedule_score
)


class ORToolsScheduler:
    """OR-Tools CP-SAT 排班演算法"""
    
    def __init__(
        self,
        employees: List[Employee],
        requirements: List[ShiftRequirement],
        time_off_requests: List[TimeOffRequest],
        pre_assigned_shifts: List[PreAssignedShift],
        start_date: date,
        num_weeks: int = 4,
        max_time_seconds: int = 300
    ):
        """
        初始化排班器
        
        Args:
            employees: 員工列表
            requirements: 班次需求列表
            time_off_requests: 請假申請列表
            pre_assigned_shifts: 預先排班列表
            start_date: 開始日期（必須是週一）
            num_weeks: 排班週數（預設 4 週）
            max_time_seconds: 最大求解時間（秒，預設 300）
        """
        self.employees = employees
        self.requirements = requirements
        self.time_off_requests = time_off_requests
        self.pre_assigned_shifts = pre_assigned_shifts
        self.start_date = start_date
        self.num_weeks = num_weeks
        self.max_time_seconds = max_time_seconds
        
        # 放寬條件設定
        self.relaxed_requirements = False
        self.relaxed_shifts = False
        self.relaxed_days_off = False
        
        # 建立需求索引
        self.requirement_map: Dict[Tuple[int, str], ShiftRequirement] = {}
        for req in requirements:
            self.requirement_map[(req.day_of_week, req.shift_time)] = req
        
        # 員工索引
        self.employee_map: Dict[str, Employee] = {emp.name: emp for emp in employees}
        
        # CP-SAT model 和 solver
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
    
    def relax_constraints(
        self,
        requirements: bool = False,
        shifts: bool = False,
        days_off: bool = False
    ):
        """
        放寬約束條件
        
        Args:
            requirements: 放寬班次需求（leader/injector）
            shifts: 放寬班次數量（允許 8-9 班）
            days_off: 放寬休假天數（允許只休 1 天）
        """
        self.relaxed_requirements = requirements
        self.relaxed_shifts = shifts
        self.relaxed_days_off = days_off
    
    def generate_month_template(self) -> List[Shift]:
        """生成一個月的排班模板（空班次）"""
        shifts = []
        shift_times = ["早", "中", "晚"]
        
        for week in range(self.num_weeks):
            for day in range(7):  # 週一到週日
                current_date = self.start_date + timedelta(weeks=week, days=day)
                
                for shift_time in shift_times:
                    shift = Shift(
                        date=current_date,
                        shift_time=shift_time,
                        assigned_employees=[]
                    )
                    shifts.append(shift)
        
        return shifts
    
    def generate_schedules(self) -> Tuple[List[Schedule], Dict]:
        """
        生成排班表
        
        Returns:
            (有效排班列表, 診斷資訊)
        """
        start_time = time.time()
        
        print(f"\n[OR-Tools] 開始 CP-SAT 求解...")
        print(f"   - 員工數: {len(self.employees)}")
        print(f"   - 總班次數: {self.num_weeks * 7 * 3}")
        print(f"   - 預先排班: {len(self.pre_assigned_shifts)}")
        print(f"   - 請假申請: {len(self.time_off_requests)}")
        print(f"   - 最大求解時間: {self.max_time_seconds}秒\n")
        
        # 生成空模板
        template_shifts = self.generate_month_template()
        
        # 建立變數和約束
        print("[*] 建立決策變數...")
        shift_vars = self._create_variables(template_shifts)
        
        print("[*] 新增硬約束...")
        self._add_constraints(template_shifts, shift_vars)
        
        print("[*] 設定目標函數...")
        self._add_objective(template_shifts, shift_vars)
        
        # 設定求解器參數
        self.solver.parameters.max_time_in_seconds = self.max_time_seconds
        self.solver.parameters.log_search_progress = True
        
        # 求解
        print("[*] 開始求解...\n")
        status = self.solver.Solve(self.model)
        
        elapsed = time.time() - start_time
        
        # 解析結果
        valid_schedules = []
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print(f"\n[SUCCESS] 找到解！（狀態: {self.solver.StatusName(status)}）")
            
            # 重建 Schedule 物件
            schedule = self._parse_solution(template_shifts, shift_vars)
            valid_schedules.append(schedule)
            
            # 顯示排班摘要
            self._print_schedule_summary(schedule)
            
        else:
            print(f"\n[FAILED] 無解（狀態: {self.solver.StatusName(status)}）")
        
        # 診斷資訊
        diagnostics = {
            "solver_status": self.solver.StatusName(status),
            "solve_time": elapsed,
            "num_conflicts": self.solver.NumConflicts(),
            "num_branches": self.solver.NumBranches(),
            "wall_time": self.solver.WallTime(),
            "relaxed_requirements": self.relaxed_requirements,
            "relaxed_shifts": self.relaxed_shifts,
            "relaxed_days_off": self.relaxed_days_off,
            "valid_count": len(valid_schedules)
        }
        
        print(f"\n[OR-Tools] 求解完成！")
        print(f"   - 總時間: {elapsed:.2f}秒")
        print(f"   - 狀態: {diagnostics['solver_status']}")
        print(f"   - 內部衝突數: {diagnostics['num_conflicts']}")
        print(f"   - 分支數: {diagnostics['num_branches']}")
        
        return valid_schedules, diagnostics
    
    def _create_variables(self, shifts: List[Shift]) -> Dict:
        """
        建立決策變數
        
        Returns:
            shift_vars[employee_idx][shift_idx] = BoolVar
        """
        shift_vars = {}
        
        for emp_idx, employee in enumerate(self.employees):
            shift_vars[emp_idx] = {}
            for shift_idx, shift in enumerate(shifts):
                var_name = f'e{emp_idx}_s{shift_idx}'
                shift_vars[emp_idx][shift_idx] = self.model.NewBoolVar(var_name)
        
        return shift_vars
    
    def _add_constraints(self, shifts: List[Shift], shift_vars: Dict):
        """新增所有約束條件"""
        
        # 1. 員工可用性約束
        self._add_availability_constraints(shifts, shift_vars)
        
        # 2. 預先排班約束
        self._add_pre_assignment_constraints(shifts, shift_vars)
        
        # 3. 班次需求約束
        self._add_shift_requirement_constraints(shifts, shift_vars)
        
        # 4. 每天班次限制約束
        self._add_daily_limit_constraints(shifts, shift_vars)
        
        # 5. 正職員工周約束
        self._add_fulltime_weekly_constraints(shifts, shift_vars)
    
    def _add_availability_constraints(self, shifts: List[Shift], shift_vars: Dict):
        """員工可用性約束（時間限制 + 請假）"""
        for emp_idx, employee in enumerate(self.employees):
            for shift_idx, shift in enumerate(shifts):
                # 檢查員工是否可上班
                if not validate_availability(shift, employee, self.time_off_requests):
                    # 強制設為 0（不能分配）
                    self.model.Add(shift_vars[emp_idx][shift_idx] == 0)
    
    def _add_pre_assignment_constraints(self, shifts: List[Shift], shift_vars: Dict):
        """預先排班約束"""
        for pre in self.pre_assigned_shifts:
            # 找到對應的班次索引
            for shift_idx, shift in enumerate(shifts):
                if shift.date == pre.date and shift.shift_time == pre.shift_time:
                    # 找到員工索引
                    for emp_idx, employee in enumerate(self.employees):
                        if employee.name == pre.employee_name:
                            # 強制分配
                            self.model.Add(shift_vars[emp_idx][shift_idx] == 1)
                            break
                    break
    
    def _add_shift_requirement_constraints(self, shifts: List[Shift], shift_vars: Dict):
        """班次需求約束（人數、Leader、打針）"""
        for shift_idx, shift in enumerate(shifts):
            day_of_week = shift.date.weekday() + 1
            requirement = self.requirement_map.get((day_of_week, shift.shift_time))
            
            if requirement is None:
                continue
            
            # 計算可用員工分類
            leader_indices = [i for i, emp in enumerate(self.employees) if emp.is_leader]
            injector_indices = [i for i, emp in enumerate(self.employees) if emp.can_inject]
            leader_or_injector_indices = [
                i for i, emp in enumerate(self.employees) 
                if emp.is_leader or emp.can_inject
            ]
            
            # 人數需求
            total_assigned = [shift_vars[i][shift_idx] for i in range(len(self.employees))]
            self.model.Add(sum(total_assigned) == requirement.num_people)
            
            # Leader 需求
            if self.relaxed_requirements:
                min_leaders = requirement.num_leaders // 2
            else:
                min_leaders = requirement.num_leaders
            
            leader_assigned = [shift_vars[i][shift_idx] for i in leader_indices]
            if leader_assigned:
                self.model.Add(sum(leader_assigned) >= min_leaders)
            
            # 打針人員需求
            if self.relaxed_requirements:
                min_injectors = requirement.num_injectors // 2
            else:
                min_injectors = requirement.num_injectors
            
            injector_assigned = [shift_vars[i][shift_idx] for i in injector_indices]
            if injector_assigned:
                self.model.Add(sum(injector_assigned) >= min_injectors)
            
            # Leader 或打針人員需求
            if self.relaxed_requirements:
                min_leader_or_injector = requirement.num_leader_or_injector // 2
            else:
                min_leader_or_injector = requirement.num_leader_or_injector
            
            leader_or_injector_assigned = [
                shift_vars[i][shift_idx] for i in leader_or_injector_indices
            ]
            if leader_or_injector_assigned:
                self.model.Add(sum(leader_or_injector_assigned) >= min_leader_or_injector)
    
    def _add_daily_limit_constraints(self, shifts: List[Shift], shift_vars: Dict):
        """每天班次限制約束（每人每天最多 3 班）"""
        # 按日期分組班次
        shifts_by_date = defaultdict(list)
        for shift_idx, shift in enumerate(shifts):
            shifts_by_date[shift.date].append(shift_idx)
        
        # 每位員工每天最多 3 班
        for emp_idx in range(len(self.employees)):
            for date_val, shift_indices in shifts_by_date.items():
                daily_shifts = [shift_vars[emp_idx][s_idx] for s_idx in shift_indices]
                self.model.Add(sum(daily_shifts) <= 3)
    
    def _add_fulltime_weekly_constraints(self, shifts: List[Shift], shift_vars: Dict):
        """正職員工周約束（每周 10 班、休 2 天）"""
        # 按週分組班次
        weeks = defaultdict(list)
        for shift_idx, shift in enumerate(shifts):
            week_key = shift.date.isocalendar()[:2]  # (year, week_number)
            weeks[week_key].append((shift_idx, shift))
        
        for emp_idx, employee in enumerate(self.employees):
            if not employee.is_fulltime:
                continue
            
            for week_key, week_shifts in weeks.items():
                shift_indices = [s_idx for s_idx, _ in week_shifts]
                
                # 每週班次數約束
                weekly_shift_vars = [shift_vars[emp_idx][s_idx] for s_idx in shift_indices]
                
                if self.relaxed_shifts:
                    # 放寬：8-10 班
                    self.model.Add(sum(weekly_shift_vars) >= 8)
                    self.model.Add(sum(weekly_shift_vars) <= 10)
                else:
                    # 嚴格：恰好 10 班
                    self.model.Add(sum(weekly_shift_vars) == 10)
                
                # 每週休假天數約束
                # 需要引入輔助變數：is_working_on_day[date] = 是否該天有上班
                shifts_by_date = defaultdict(list)
                for s_idx, shift in week_shifts:
                    shifts_by_date[shift.date].append(s_idx)
                
                is_working_on_day = {}
                for date_val, day_shift_indices in shifts_by_date.items():
                    # 建立輔助布林變數
                    day_var = self.model.NewBoolVar(f'e{emp_idx}_week{week_key}_d{date_val}_working')
                    is_working_on_day[date_val] = day_var
                    
                    # 如果該天任一班次被分配，則 day_var = 1
                    day_shift_vars = [shift_vars[emp_idx][s_idx] for s_idx in day_shift_indices]
                    
                    # day_var == 1 if any(day_shift_vars) == 1
                    # 使用 AddMaxEquality: day_var = max(day_shift_vars)
                    self.model.AddMaxEquality(day_var, day_shift_vars)
                
                # 工作天數限制
                work_days = list(is_working_on_day.values())
                
                if self.relaxed_days_off:
                    # 放寬：最多工作 6 天（至少休 1 天）
                    self.model.Add(sum(work_days) <= 6)
                else:
                    # 嚴格：最多工作 5 天（至少休 2 天）
                    self.model.Add(sum(work_days) <= 5)
    
    def _add_objective(self, shifts: List[Shift], shift_vars: Dict):
        """設定目標函數（偏好：同一天上兩班）"""
        # 按日期分組班次
        shifts_by_date = defaultdict(list)
        for shift_idx, shift in enumerate(shifts):
            shifts_by_date[shift.date].append(shift_idx)
        
        # 建立 bonus 變數
        bonus_vars = []
        
        for emp_idx in range(len(self.employees)):
            for date_val, shift_indices in shifts_by_date.items():
                if len(shift_indices) < 2:
                    continue
                
                # 該員工在這天的班次數
                daily_shifts = [shift_vars[emp_idx][s_idx] for s_idx in shift_indices]
                
                # 建立 bonus 變數：如果恰好上 2 班，則 bonus = 1
                bonus_var = self.model.NewBoolVar(f'bonus_e{emp_idx}_d{date_val}')
                
                # bonus_var == 1 當且僅當 sum(daily_shifts) == 2
                # 這需要用兩個約束來實現：
                # 1. sum(daily_shifts) >= 2 => bonus_var 可以是 1
                # 2. sum(daily_shifts) == 2 => bonus_var 必須是 1
                # 3. sum(daily_shifts) != 2 => bonus_var 必須是 0
                
                # 簡化方法：使用線性約束
                # bonus_var = 1 if sum == 2, else 0
                # 我們使用以下方式：
                # sum >= 2 * bonus
                # sum <= 2 + M * (1 - bonus)  其中 M 是大數
                
                daily_sum = sum(daily_shifts)
                # 如果 bonus = 1，則 sum 必須 >= 2
                self.model.Add(daily_sum >= 2 * bonus_var)
                # 如果 bonus = 1，則 sum 必須 <= 2（因為最多3班，這裡允許誤差）
                self.model.Add(daily_sum <= 2 + (len(shift_indices) - 2) * (1 - bonus_var))
                
                bonus_vars.append(bonus_var)
        
        # 最大化總 bonus（每個 bonus 計 10 分）
        if bonus_vars:
            self.model.Maximize(sum(bonus_vars) * 10)
    
    def _parse_solution(self, shifts: List[Shift], shift_vars: Dict) -> Schedule:
        """解析求解結果並重建 Schedule 物件"""
        # 複製 shifts 以避免修改原始物件
        result_shifts = []
        
        for shift_idx, shift in enumerate(shifts):
            assigned_employees = []
            
            for emp_idx, employee in enumerate(self.employees):
                if self.solver.Value(shift_vars[emp_idx][shift_idx]):
                    assigned_employees.append(employee)
            
            result_shift = Shift(
                date=shift.date,
                shift_time=shift.shift_time,
                assigned_employees=assigned_employees
            )
            result_shifts.append(result_shift)
        
        return Schedule(shifts=result_shifts)
    
    def _print_schedule_summary(self, schedule: Schedule):
        """顯示排班摘要"""
        print("\n=== 排班統計 ===")
        
        # 統計每人班次
        for employee in self.employees:
            shifts_list = schedule.get_employee_shifts(employee.name)
            print(f"{employee.name}: 共 {len(shifts_list)} 班")
        
        # 計算偏好分數
        score = calculate_schedule_score(schedule)
        print(f"\n偏好分數: {score}")
