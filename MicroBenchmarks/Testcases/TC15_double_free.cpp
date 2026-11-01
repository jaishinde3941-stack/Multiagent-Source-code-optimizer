// Category: Memory Management Errors
// Error: Double free

#include <iostream>

int main() {
    int* ptr = new int(42);
    
    std::cout << "Value: " << *ptr << std::endl;
    
    delete ptr;
    delete ptr;  // ERROR: Double free
    
    return 0;
}
