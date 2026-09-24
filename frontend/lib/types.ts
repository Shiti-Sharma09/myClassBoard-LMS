export type Role = "teacher" | "student" | "parent" | "admin";

export interface StudentInfo {
  id: number;
  name: string;
  class_name: string;
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  student: StudentInfo | null; // set for students
  child: StudentInfo | null; // set for parents
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface DemoAccount {
  label: string;
  role: Role;
  email: string;
  password: string;
}
