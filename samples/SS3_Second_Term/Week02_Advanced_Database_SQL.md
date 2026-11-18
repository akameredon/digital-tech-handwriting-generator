**Class:** SS3  
**Term:** Second Term  
**Week:** 2  
**Topic:** Advanced Database Management – SQL Basics

---

**Behavioral Learning Objectives**  
By the end of this lesson, students should be able to:  
1. Define SQL and state its purpose.  
2. Write simple SELECT statements to retrieve data.  
3. Use WHERE, ORDER BY and basic filtering.  
4. Explain the importance of databases in real systems.

---

**Key Concepts / Definitions**  
- **SQL (Structured Query Language)**: The standard language used to communicate with relational databases.  
- **Database**: An organised collection of data stored electronically.  
- **Table**: A set of data organised in rows and columns.  
- **SELECT**: The SQL command used to retrieve data from a table.  
- **WHERE**: Used to filter records based on a condition.  
- **ORDER BY**: Used to sort the results.

---

**Step-by-Step Conceptual Explanation**  

1. Almost every modern system (school portal, bank, hospital, JAMB) stores information in databases.  
2. SQL allows us to ask questions of the database in a structured way.  
3. The most common operation is retrieving data with SELECT.  
4. We can filter results (WHERE) and sort them (ORDER BY).  
5. Understanding basic SQL prepares students for further studies in computer science, data analysis and software development.

---

**Practical / Worked Example**

```sql
-- Retrieve all students
SELECT * FROM Students;

-- Retrieve only names and scores of students who scored 70 or above
SELECT name, score FROM Students
WHERE score >= 70
ORDER BY score DESC;
```

---

**Class Activity / Guided Practice**  
Students write SQL statements to:  
1. Select all columns from a table called Books.  
2. Select title and author where year > 2020.  
3. Order the results by title.

---

**End-of-Lesson Quick Test**  
1. What does SQL stand for?  
2. What is the purpose of the SELECT statement?  
3. What does the WHERE clause do?  
4. What does ORDER BY do?  
5. True or False: SQL can only be used with Microsoft Excel.

---

**Assignment**  
Design a simple table for student records (name, class, score). Write five SQL queries that retrieve useful information from that table.
