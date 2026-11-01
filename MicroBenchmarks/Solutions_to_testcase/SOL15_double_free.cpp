// Category: Memory Management Errors (Success Case)
// Expected Result: Pointer should be deleted only once and set to nullptr

#include <iostream>

int main() {
    int* ptr = new int(42);
    
    std::cout << "Value: " << *ptr << std::endl;
    
    if (ptr != nullptr) {
        delete ptr;
        ptr = nullptr;  // SUCCESS: Only freed once and set to nullptr
    }
    
    return 0;
}
