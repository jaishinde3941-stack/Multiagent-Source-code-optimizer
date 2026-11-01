// Category: Control Flow Errors
// Error: Empty if body with semicolon

#include <iostream>

int main() {
    int x = 5;
    
    if (x > 0);  // ERROR: Semicolon makes if body empty
    {
        std::cout << "x is positive" << std::endl;  // Always executes
    }
    
    return 0;
}
