// Category: Memory Management Errors
// Error: Memory leak in loop

#include <iostream>

int main() {
    for (int i = 0; i < 100; i++) {
        int* ptr = new int(i);  // ERROR: Memory leak in loop - never freed
        std::cout << *ptr << " ";
    }
    std::cout << std::endl;
    
    return 0;
}
