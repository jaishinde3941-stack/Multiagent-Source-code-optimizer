// Category: Division by Zero (Success Case)
// Expected Result: Denominator should be non-zero

#include <iostream>

int main() {
    int numerator = 100;
    int divisor = 1;  // SUCCESS: Changed to a non-zero value
    
    int result = numerator / divisor;
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
