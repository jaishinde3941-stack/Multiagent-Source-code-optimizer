// Category: Memory Management Errors (Success Case)
// Expected Result: Free memory in each loop iteration

#include <iostream>

int main() {
    for (int i = 0; i < 100; i++) {
        int* ptr = new int(i);
        std::cout << *ptr << " ";
        delete ptr;  // SUCCESS: Freed in loop
    }
    std::cout << std::endl;
    
    return 0;
}
