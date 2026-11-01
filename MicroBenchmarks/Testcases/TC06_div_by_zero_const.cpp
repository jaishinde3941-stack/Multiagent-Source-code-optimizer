// Category: Division by Zero
// Error: Direct division by zero constant

#include <iostream>

int main() {
    int numerator = 100;
    int result = numerator / 0;  // ERROR: Division by zero
    
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
