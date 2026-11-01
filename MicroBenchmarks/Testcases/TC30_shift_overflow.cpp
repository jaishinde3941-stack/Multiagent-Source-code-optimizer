// Category: Integer Errors
// Error: Shift overflow

#include <iostream>

int main() {
    int value = 1;
    int result = value << 32;  // ERROR: Shifting by width of type is undefined
    
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
