// Category: Pointer Errors (Success Case)
// Expected Result: Check if pointer is null before dereferencing

#include <iostream>

int main() {
    int val = 42;
    int* ptr = &val;  // SUCCESS: Initialized to valid memory
    
    if (ptr != nullptr) {
        *ptr = 42;
        std::cout << "Value: " << *ptr << std::endl;
    }
    
    return 0;
}
