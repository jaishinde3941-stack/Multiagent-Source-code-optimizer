// Category: Uninitialized Variables (Success Case)
// Expected Result: Boolean flag should be initialized before use in condition

#include <iostream>

int main() {
    bool flag = false;  // SUCCESS: Initialized to false
    
    if (flag) {
        std::cout << "Flag is true" << std::endl;
    } else {
        std::cout << "Flag is false" << std::endl;
    }
    
    return 0;
}
