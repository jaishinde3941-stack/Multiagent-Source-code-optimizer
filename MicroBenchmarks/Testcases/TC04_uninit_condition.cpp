// Category: Uninitialized Variables
// Error: Using uninitialized variable in condition

#include <iostream>

int main() {
    bool flag;
    
    if (flag) {  // ERROR: flag is uninitialized
        std::cout << "Flag is true" << std::endl;
    } else {
        std::cout << "Flag is false" << std::endl;
    }
    
    return 0;
}
