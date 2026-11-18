**Class:** SS3  
**Term:** First Term  
**Week:** 2  
**Topic:** Advanced Programming I – Functions and Arrays/Lists

---

**Behavioral Learning Objectives**  
By the end of this lesson, students should be able to:  
1. Define a function and explain why functions are useful.  
2. Write and call simple functions in Python.  
3. Explain what a list (array) is.  
4. Perform basic operations on lists (create, access, append).

---

**Key Concepts / Definitions**  
- **Function**: A reusable block of code that performs a specific task.  
- **Parameter**: A value that is passed into a function.  
- **Return value**: The result that a function sends back.  
- **List**: An ordered collection of items in Python (similar to an array in other languages).  
- **Index**: The position of an item in a list (starting from 0).

---

**Step-by-Step Conceptual Explanation**  

1. Functions help us avoid repeating code and make programs easier to read and maintain.  
2. Once a function is defined, it can be called many times with different values.  
3. Lists allow us to store multiple related values under one name.  
4. We can access individual items using their index and add new items using `append()`.  
5. Combining functions and lists is a powerful way to solve real programming problems.

---

**Practical / Worked Example**

```python
def calculate_average(scores):
    total = sum(scores)
    return total / len(scores)

student_scores = [75, 68, 82, 90, 71]
avg = calculate_average(student_scores)
print("Average score:", avg)
```

---

**Class Activity / Guided Practice**  
Students write a function that takes a list of five numbers and returns the highest number. They test it with different lists.

---

**End-of-Lesson Quick Test**  
1. What is a function?  
2. Why do we use functions in programming?  
3. What is a list in Python?  
4. What is the index of the first item in a list?  
5. True or False: A function can only be used once in a program.

---

**Assignment**  
Write a Python program that:  
1. Creates a list of five subject scores.  
2. Defines a function to calculate the total.  
3. Defines another function to calculate the average.  
4. Prints both results clearly.
