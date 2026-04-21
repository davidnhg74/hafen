-- Oracle HR Schema (simplified for testing)

CREATE TABLE employees (
  employee_id NUMBER(6) PRIMARY KEY,
  first_name VARCHAR2(20),
  last_name VARCHAR2(25) NOT NULL,
  email VARCHAR2(25),
  phone_number VARCHAR2(20),
  hire_date DATE NOT NULL,
  job_id VARCHAR2(10),
  salary NUMBER(8,2),
  commission_pct NUMBER(2,2),
  manager_id NUMBER(6),
  department_id NUMBER(4)
);

CREATE TABLE departments (
  department_id NUMBER(4) PRIMARY KEY,
  department_name VARCHAR2(30) NOT NULL,
  manager_id NUMBER(6),
  location_id NUMBER(4)
);

CREATE VIEW emp_view AS
SELECT employee_id, first_name, last_name, salary
FROM employees;

CREATE SEQUENCE employees_seq START WITH 207 INCREMENT BY 1;

CREATE OR REPLACE FUNCTION get_employee_salary(p_emp_id NUMBER) RETURN NUMBER AS
  v_salary employees.salary%TYPE;
BEGIN
  SELECT salary INTO v_salary FROM employees WHERE employee_id = p_emp_id;
  RETURN v_salary;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    RETURN 0;
END get_employee_salary;
/

CREATE OR REPLACE PROCEDURE raise_salary(p_emp_id NUMBER, p_increase NUMBER) AS
  v_current_salary employees.salary%TYPE;
BEGIN
  SELECT salary INTO v_current_salary FROM employees WHERE employee_id = p_emp_id FOR UPDATE;
  UPDATE employees SET salary = v_current_salary + p_increase WHERE employee_id = p_emp_id;
  COMMIT;
END raise_salary;
/

CREATE OR REPLACE PACKAGE emp_pkg AS
  PROCEDURE hire_employee(p_first_name VARCHAR2, p_last_name VARCHAR2, p_job_id VARCHAR2);
  FUNCTION calc_annual_comp(p_salary NUMBER, p_commission NUMBER) RETURN NUMBER;
END emp_pkg;
/

CREATE OR REPLACE PACKAGE BODY emp_pkg AS
  PROCEDURE hire_employee(p_first_name VARCHAR2, p_last_name VARCHAR2, p_job_id VARCHAR2) AS
  BEGIN
    INSERT INTO employees (employee_id, first_name, last_name, job_id, hire_date)
    VALUES (employees_seq.NEXTVAL, p_first_name, p_last_name, p_job_id, SYSDATE);
    COMMIT;
  END hire_employee;

  FUNCTION calc_annual_comp(p_salary NUMBER, p_commission NUMBER) RETURN NUMBER AS
  BEGIN
    RETURN (p_salary * 12) + (p_salary * 12 * NVL(p_commission, 0));
  END calc_annual_comp;
END emp_pkg;
/

CREATE OR REPLACE TRIGGER emp_audit_trg
AFTER INSERT ON employees
FOR EACH ROW
BEGIN
  INSERT INTO audit_log (table_name, action, timestamp) VALUES ('EMPLOYEES', 'INSERT', SYSDATE);
END emp_audit_trg;
/

-- Tier B: CONNECT BY example
CREATE OR REPLACE PROCEDURE get_hierarchy(p_emp_id NUMBER) AS
BEGIN
  FOR emp IN (
    SELECT employee_id, first_name, LEVEL
    FROM employees
    START WITH manager_id IS NULL
    CONNECT BY PRIOR employee_id = manager_id
  ) LOOP
    DBMS_OUTPUT.PUT_LINE(LPAD(' ', (emp.LEVEL - 1) * 2) || emp.first_name);
  END LOOP;
END get_hierarchy;
/

-- Tier B: MERGE example
CREATE OR REPLACE PROCEDURE sync_salaries(p_dept_id NUMBER) AS
BEGIN
  MERGE INTO employees e
  USING (SELECT employee_id, salary FROM salary_stage WHERE department_id = p_dept_id) s
  ON (e.employee_id = s.employee_id)
  WHEN MATCHED THEN
    UPDATE SET e.salary = s.salary
  WHEN NOT MATCHED THEN
    INSERT (employee_id, salary) VALUES (s.employee_id, s.salary);
  COMMIT;
END sync_salaries;
/

-- Tier B: %TYPE / %ROWTYPE
CREATE OR REPLACE PROCEDURE process_employee(p_emp_id NUMBER) AS
  v_emp employees%ROWTYPE;
  v_salary employees.salary%TYPE;
BEGIN
  SELECT * INTO v_emp FROM employees WHERE employee_id = p_emp_id;
  v_salary := v_emp.salary * 1.1;
  UPDATE employees SET salary = v_salary WHERE employee_id = p_emp_id;
END process_employee;
/

-- Tier B: EXECUTE IMMEDIATE
CREATE OR REPLACE PROCEDURE dynamic_query(p_table_name VARCHAR2) AS
  v_count NUMBER;
BEGIN
  EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM ' || p_table_name INTO v_count;
  DBMS_OUTPUT.PUT_LINE('Count: ' || v_count);
END dynamic_query;
/

-- Tier C: AUTONOMOUS_TRANSACTION
CREATE OR REPLACE PROCEDURE log_activity(p_activity VARCHAR2) AS
  PRAGMA AUTONOMOUS_TRANSACTION;
BEGIN
  INSERT INTO activity_log (activity, log_date) VALUES (p_activity, SYSDATE);
  COMMIT;
END log_activity;
/

-- Tier C: DBMS_SCHEDULER (flagged for human review)
BEGIN
  DBMS_SCHEDULER.CREATE_JOB (
    job_name => 'nightly_sync',
    job_type => 'PLSQL_BLOCK',
    job_action => 'BEGIN sync_salaries(10); END;',
    repeat_interval => 'FREQ=DAILY;BYHOUR=22'
  );
END;
/
