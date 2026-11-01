// Category: Logic Errors
// Error: Infinite recursion

#include <iostream>

int factorial(int n) {
    // ERROR: Missing base case check
    return n * factorial(n - 1);  // Will recurse forever (stack overflow)
}

int main() {
    int result = factorial(5);
    std::cout << "Factorial: " << result << std::endl;
    
    return 0;
}
