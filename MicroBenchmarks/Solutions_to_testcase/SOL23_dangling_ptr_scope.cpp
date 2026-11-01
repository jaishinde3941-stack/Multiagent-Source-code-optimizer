// Category: Pointer Errors (Success Case)
// Expected Result: Do not return pointer to local variable; use static or heap allocation

#include <iostream>

int* getPointer() {
    static int localVar = 42;  // SUCCESS: Used static to persist across scope
    return &localVar;
}

int main() {
    int* ptr = getPointer();
    if (ptr != nullptr) {
        std::cout << "Value: " << *ptr << std::endl;
    }
    
    return 0;
}
