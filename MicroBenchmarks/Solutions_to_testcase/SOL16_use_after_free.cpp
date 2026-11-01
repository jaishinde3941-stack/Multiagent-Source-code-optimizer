// Category: Memory Management Errors (Success Case)
// Expected Result: Do not use pointer after it is freed

#include <iostream>

int main() {
    int* ptr = new int(42);
    
    // Use it before delete
    std::cout << "Value: " << *ptr << std::endl;
    
    delete ptr;
    ptr = nullptr;  // SUCCESS: Set to nullptr and never used again
    
    return 0;
}
