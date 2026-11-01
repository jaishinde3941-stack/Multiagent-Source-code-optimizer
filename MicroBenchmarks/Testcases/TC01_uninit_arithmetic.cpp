// Category: Uninitialized Variables
// Error: Using uninitialized variable in arithmetic operation

#include <iostream>

int main() {
    int x;
    int y = 10;
    
    int result = x + y;  // ERROR: x is uninitialized
    std::cout << "Result: " << result << std::endl;
    
    return 0;
}
