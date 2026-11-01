// Category: Pointer Errors
// Error: Dangling pointer after scope

#include <iostream>

int* getPointer() {
    int localVar = 42;
    return &localVar;  // ERROR: Returning pointer to local variable
}

int main() {
    int* ptr = getPointer();
    std::cout << "Value: " << *ptr << std::endl;  // Dangling pointer
    
    return 0;
}
