// Category: Memory Management Errors
// Error: Memory leak - allocated memory never freed

#include <iostream>

int main() {
    int* ptr = new int[100];  // ERROR: Memory leak - never deleted
    
    for (int i = 0; i < 100; i++) {
        ptr[i] = i;
    }
    
    std::cout << "Sum of first element: " << ptr[0] << std::endl;
    
    return 0;  // Memory leaked here
}
