// Category: Type Errors
// Error: Pointer type confusion

#include <iostream>

int main() {
    double d = 3.14159;
    int* intPtr = (int*)&d;  // ERROR: Type punning, undefined behavior
    
    std::cout << "As int: " << *intPtr << std::endl;
    
    return 0;
}
