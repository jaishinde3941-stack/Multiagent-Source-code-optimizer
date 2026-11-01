// Category: Uninitialized Variables (Success Case)
// Expected Result: Pointer should be initialized or allocated before use

#include <iostream>

int main() {
    int val = 42;
    int* ptr = &val;  // SUCCESS: Pointing to valid memory
    
    *ptr = 42;
    std::cout << "Value: " << *ptr << std::endl;
    
    return 0;
}
