// Category: Division by Zero (Success Case)
// Expected Result: Denominator variable should be checked before division

#include <iostream>

int main() {
    int numerator = 100;
    int denominator = 0;
    
    if (denominator != 0) {  // SUCCESS: Checked for zero before division
        int result = numerator / denominator;
        std::cout << "Result: " << result << std::endl;
    } else {
        std::cout << "Error: Division by zero avoided" << std::endl;
    }
    
    return 0;
}
