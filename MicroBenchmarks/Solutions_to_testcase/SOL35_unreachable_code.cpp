// Category: Logic Errors (Success Case)
// Expected Result: Avoid unreachable code

#include <iostream>

int getValue() {
    std::cout << "Executing logic before return" << std::endl;  // SUCCESS: Moved code before return
    return 42;
}

int main() {
    std::cout << getValue() << std::endl;
    return 0;
}
