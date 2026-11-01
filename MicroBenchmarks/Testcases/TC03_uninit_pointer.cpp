// Category: Uninitialized Variables
// Error: Using uninitialized pointer

#include <iostream>

int main() {
    int* ptr;
    
    *ptr = 42;  // ERROR: ptr is uninitialized (dangling pointer write)
    std::cout << "Value: " << *ptr << std::endl;
    
    return 0;
}
