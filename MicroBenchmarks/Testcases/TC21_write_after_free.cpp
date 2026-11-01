// Category: Memory Management Errors
// Error: Writing to freed memory

#include <iostream>

int main() {
    int* ptr = new int(10);
    
    delete ptr;
    
    *ptr = 20;  // ERROR: Writing to freed memory
    
    return 0;
}
