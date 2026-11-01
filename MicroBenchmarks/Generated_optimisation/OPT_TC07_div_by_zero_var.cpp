// Category: Division by Zero
// Error: Division by zero through variable

#include <iostream>

int main() {
    int numerator = 100;
    int denominator = 0;
    
    int result = numerator / denominator;  // ERROR: Division by zero via variable
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
