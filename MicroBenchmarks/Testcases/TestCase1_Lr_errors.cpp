#include <iostream>

int main() {
    int x;
    int y = 10;

    // Use of uninitialized variable
    int sum = x + y;

    // Missing parentheses in function call
    std::cout << "Sum is: " << sum << std::endl;

    // Logical error: division by zero
    int result = y / 0;

    // No return statement
}
