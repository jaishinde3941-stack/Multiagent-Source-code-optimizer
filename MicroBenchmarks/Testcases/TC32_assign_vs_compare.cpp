// Category: Logic Errors
// Error: Assignment instead of comparison

#include <iostream>

int main() {
    int x = 5;
    
    if (x = 10) {  // ERROR: Assignment (=) instead of comparison (==)
        std::cout << "x equals 10" << std::endl;
    }
    
    std::cout << "x is now: " << x << std::endl;  // x is now 10!
    
    return 0;
}
