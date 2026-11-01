// Category: Resource Leaks
// Error: Lost pointer to allocated memory

#include <iostream>

int main() {
    int* ptr = new int(42);
    
    ptr = new int(100);  // ERROR: Original allocation lost - memory leak
    
    std::cout << "Value: " << *ptr << std::endl;
    delete ptr;
    
    return 0;
}
