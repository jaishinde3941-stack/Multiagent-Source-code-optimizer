// Category: Memory Management Errors
// Error: Use after free

#include <iostream>

int main() {
    int* ptr = new int(42);
    
    delete ptr;
    
    std::cout << "Value: " << *ptr << std::endl;  // ERROR: Use after free
    
    return 0;
}
