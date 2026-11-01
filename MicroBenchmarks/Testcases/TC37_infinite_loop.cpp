// Category: Control Flow Errors
// Error: Infinite loop

#include <iostream>

int main() {
    int i = 0;
    
    while (i < 10) {
        std::cout << i << " ";
        // ERROR: Missing i++ increment - infinite loop
    }
    
    std::cout << std::endl;
    return 0;
}
