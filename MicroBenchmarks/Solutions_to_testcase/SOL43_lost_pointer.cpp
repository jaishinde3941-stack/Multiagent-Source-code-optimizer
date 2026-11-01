// Category: Resource Leaks (Success Case)
// Expected Result: Free old allocation before assigning a new one to the pointer

#include <iostream>

int main() {
    int* ptr = new int(42);
    
    // SUCCESS: Delete old memory before reassigning
    delete ptr;
    ptr = new int(100);
    
    std::cout << "Value: " << *ptr << std::endl;
    delete ptr;
    
    return 0;
}
