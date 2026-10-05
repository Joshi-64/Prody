# Prody - Student Productivity Platform

Prody is a web-based productivity application built for students. This repository contains the core User Management and Database subsystems developed for Sprint 2.

---

## Tech Stack
* **Language:** Python
* **Backend Framework:** Flask
* **Database:** MySQL 8.0
* **Security:** Werkzeug (Password hashing via `scrypt`)

---

## Getting Started

### 1. Database Setup
Ensure your local MySQL Server is running. Create the database and user table using the schema below (or run `schema.sql`):

```sql
CREATE DATABASE IF NOT EXISTS prody_dev;
USE prody_dev;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('student', 'admin') NOT NULL DEFAULT 'student',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);