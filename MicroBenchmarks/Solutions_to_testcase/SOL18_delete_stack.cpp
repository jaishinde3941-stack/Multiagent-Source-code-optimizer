// Category: Memory Management Errors (Success Case)
// Expected Result: Do not delete stack-allocated memory

#include <iostream>

int main() {
    int stackVar = 42;
    // int* ptr = &stackVar;  // Not necessary to pointer-ize if not dynamically allocated
    
    std::cout << "Value: " << stackVar << std::endl;
    
    // delete ptr;  // SUCCESS: Removed invalid delete
    
    return 0;
}
