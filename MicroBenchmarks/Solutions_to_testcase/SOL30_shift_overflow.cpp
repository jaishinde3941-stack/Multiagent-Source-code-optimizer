// Category: Integer Errors (Success Case)
// Expected Result: Ensure shift amount is less than width of type

#include <iostream>

int main() {
    int value = 1;
    int shiftAmount = 31;  // SUCCESS: Shift amount within valid range (0-31)
    
    int result = value << shiftAmount;
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
