// Category: Pointer Errors
// Error: Null pointer dereference

#include <iostream>

int main() {
    int* ptr = nullptr;
    
    *ptr = 42;  // ERROR: Null pointer dereference
    std::cout << "Value: " << *ptr << std::endl;
    
    return 0;
}
