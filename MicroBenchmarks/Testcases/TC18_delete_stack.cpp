// Category: Memory Management Errors
// Error: Delete on stack variable

#include <iostream>

int main() {
    int stackVar = 42;
    int* ptr = &stackVar;
    
    delete ptr;  // ERROR: Deleting stack-allocated memory
    
    return 0;
}
