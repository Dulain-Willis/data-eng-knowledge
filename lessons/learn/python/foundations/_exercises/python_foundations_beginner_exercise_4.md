# Python Foundations: Beginner - Precedence and augmented assignment (placeholder)

Lesson: [python_foundations_beginner.md](../python_foundations_beginner.md)

> **Placeholder.** The real exercise for this spot is not mapped yet. The lesson links here where the exercise sat; the text below only referred to the exercise, so it was moved here from the lesson. Replace this file with the exercise when it is mapped.

## Text moved from the lesson

The broken line divides only `discount_cents` by 100, because `/` binds tighter than `-`, so the output is 14992.0, a cent total with 5 dollars subtracted from it. Wrapping the subtraction in parentheses makes the whole cent amount divide, and the result is 144.97 dollars. A bug like this prints a plausible number every time it runs, which is why a total that is 100 times too large is worth a parenthesis check before anything else.
