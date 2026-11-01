// Category: Logic Errors (Success Case)
// Expected Result: Recursive function must have a correct base case

#include <iostream>

int factorial(int n) {
    // SUCCESS: Added correct base case
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int main() {
    int result = factorial(5);
    std::cout << "Factorial: " << result << std::endl;
    
    return 0;
}
